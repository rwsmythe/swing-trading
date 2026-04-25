# Harness-vs-Production Parity Check (Hypothesis 5)

**Date:** 2026-04-25
**Companion to:** `./candidate-sparsity-diagnostic.md` (immediate predecessor; identifies hypothesis 5 as out-of-scope at §"Findings" point 8 and §"What this diagnostic does NOT say").
**Brief:** `../../docs/harness-vs-production-parity-brief.md`.
**Status:** Pre-registration (D1) — descriptive only; no production-code recommendations.

---

## Pre-registration

*This section is committed BEFORE D2 (implementation), D3 (data run), and D4 (findings) per the discipline established in `./earnings-proximity-exclusion-results.md` §"Pre-registration." The git history must show D1 → D2 → D3 → D4 ordering for the study to be honestly pre-registered. Subsequent sections (Run details, Results, Tier classification, Disagreement characterization, Findings, …) will be appended in D4 only AFTER D3's outputs are inspected. The pre-registration sections below — Hypothesis, Comparison primitive, Decision tiers, Anti-rationalization clause, Sample-size limitation, Surfaces NOT compared, Provenance commitments, Run procedure — are frozen at D1 and will not be modified post-data.*

### Hypothesis statement

> The full harness pipeline (universe loading + RS computation + OHLCV slicing + `evaluate_one` + bucket assignment) produces identical bucket assignments and identical per-criterion `pass`/`fail`/`na` results as production's `_step_evaluate`, when fed identical inputs (same universe, same date, same `current_equity`, same OHLCV).

This is hypothesis 5 from the candidate-sparsity diagnostic. The diagnostic measured a residual ~50× gap between its most-permissive cell (Russell 3000 5×: 0.00977 % per ticker-day) and the Session 2a production anchor (~0.500 % per ticker-day; n = 2 / ~400 ticker-days; Wilson 95 % CI [0.137 %, 1.806 %]). Three named candidates for the residual — Finviz pre-screening, time-period regime, harness-vs-production parity drift — are listed at the diagnostic's §"Findings" point 8. This study scopes to the third only.

### Comparison primitive

For one production `evaluation_runs` row R:

- **Production side:** `swing.data.repos.candidates.fetch_candidates_for_run(conn, R)` returns `Candidate` objects with `bucket` and `criteria` populated. Per-(ticker, criterion) results are read directly from `candidate_criteria`.
- **Harness side:** for each ticker T in R's evaluated set (i.e., tickers with non-empty `criteria` on the production side; `bucket ∈ {aplus, watch, skip}`), build a `CandidateContext(...)` and call `swing.evaluation.evaluator.evaluate_one(ctx)`. Inputs are reconstructed to mirror `swing/pipeline/runner.py:_step_evaluate` exactly — same universe (full rs-universe per `BatchContext.universe_tickers`), same date, same `current_equity` (derived via the same `sizing_equity(real_equity=current_equity(...), floor=...)` formula), same OHLCV (re-fetched via `swing.prices.PriceFetcher` against the production cache).
- **Comparison:** per-ticker `prod_bucket == harness_bucket` (bucket parity); per-(ticker, criterion) `prod_result == harness_result` for every criterion present in either side, where mismatched-presence (criterion present on one side but absent on the other) counts as disagreement.

Excluded from the comparison set:

- Tickers production placed in `bucket = 'excluded'` (operator-held positions or ETF/fund blocklist). Production sets `criteria=()` for these; the harness reconstruction would either replicate the exclusion (trivially producing 100 % agreement that adds nothing) or skip the exclusion (producing systematic non-comparable disagreement). Excluding them is the only honest choice.
- Tickers production placed in `bucket = 'error'` (transient OHLCV-fetch failures). Harness re-fetch may succeed or may fail differently; either outcome is uninformative about parity.

The comparison set is therefore `{T | prod_bucket(T) ∈ {'aplus', 'watch', 'skip'}}`, and the per-criterion denominator is the count of (ticker, criterion) pairs over that set.

### Decision tiers (frozen pre-data)

Computed across all tickers in the comparison set for the chosen production `evaluation_run` R.

- **Tier 1 — Parity holds.** Bucket agreement ≥ 99 % AND per-criterion agreement ≥ 99 %, where per-criterion agreement is `matching_pairs / total_pairs` over all (ticker, criterion) tuples in the comparison set, with mismatched-presence counted as disagreement. Interpretation: harness and production are equivalent classifiers for this run's inputs. The residual ~50× rate gap to the Session 2a anchor must therefore be attributable to (a) Finviz pre-screening, (b) time-period regime, (c) Session 2a anchor noise (its CI is consistent with true rates as low as 0.05 %), or (d) some unidentified factor outside the parity scope.

- **Tier 2 — Minor drift.** 95 % ≤ bucket agreement < 99 % OR 95 % ≤ per-criterion agreement < 99 %. Interpretation: drift exists but is unlikely to dominate the rate gap. Characterize the divergent surfaces; do not act in this study.

- **Tier 3 — Drift-dominant.** Bucket agreement < 95 % OR per-criterion agreement < 95 %. Interpretation: drift plausibly explains a meaningful fraction of the residual rate gap. Warrants follow-on: either harness fix (if production is correct) or production audit (if harness's logic is in fact correct). Tier 3 does NOT in itself recommend either fix; it triggers a separate scoping conversation with the operator.

The two metrics (bucket agreement and per-criterion agreement) are evaluated independently; the worse of the two governs the tier (i.e., a run with 99.5 % bucket agreement but 96 % per-criterion agreement is Tier 2, not Tier 1).

### Anti-rationalization clause

The tier boundaries (99 / 95) are frozen at D1. If post-data results sit near a boundary (e.g., 98.7 % per-criterion agreement), the result IS Tier 2; no boundary adjustment to push it into Tier 1. The D4 findings writeup may discuss the proximity but the classification is what it is. D5+ adversarial-review fixes can clarify framing or correct factual errors but cannot move tier boundaries.

### Sample-size limitation

A single production run typically has ~30–50 tickers per Finviz CSV (eval 15, the auto-selected target at D1, has 81 candidates of which 80 are evaluated through `evaluate_one`). With 18 criteria per ticker (TT1–TT8 + 9 VCP + 1 risk), the per-criterion denominator is ~1,440 pairs for eval 15 — at the upper end of the brief's anticipated 420–700 range, large enough to make the tier classification non-trivial but small enough that the classification is descriptive of THIS RUN, not of the harness-vs-production system globally. Multi-run characterization is the named follow-on if the operator wants tighter inference; it is explicitly out-of-scope here.

### Surfaces explicitly NOT compared

These are out of comparison scope. Their divergence is a known harness-vs-production design difference, not "drift," and would falsely inflate disagreement counts if compared:

- **A+ signal `entry_target` / `initial_stop` / `pivot`.** Production rounds and stores these to DB columns (`pivot REAL`, `initial_stop REAL`); the harness retains floats. If any A+ candidates appear, compare numerics by tolerance (≤ $0.01 absolute) or exclude from the parity assertion. Eval 15 has zero A+; this surface is unlikely to bind on the chosen run.
- **Evaluation timestamp.** The harness uses run-now `_dt.now()`; production used pipeline-run-time. Timestamps are not part of the parity comparison.
- **`Candidate.notes`.** Production sets ticker-specific notes (e.g., `'open position'` for excluded tickers, `'OHLCV fetch failed'` for error tickers). The harness reconstruction does not reproduce these; comparison is over `bucket` and `criteria` only, not `notes`.
- **Bucket `error`.** Production may set `bucket='error'` for tickers whose OHLCV fetch raised an exception; the harness re-run may or may not encounter the same transient failure. Tickers in `bucket='error'` on the production side are excluded from the comparison set per §"Comparison primitive."
- **`rs_method`, `pattern_tag`, summary scalars (`adr_pct`, `tight_streak`, …).** These are derived from the same per-criterion results that the comparison primitive already compares; comparing them again would double-count any disagreement. Bucket + per-(ticker, criterion) is the canonical surface.

### Provenance commitments

The D3 `run_manifest.json` will record:

- Harness git SHA at the time of the D3 run (post-D2 commit).
- Production `evaluation_run_id`, `action_session_date`, `data_asof_date`, `finviz_csv_path`, `finviz_csv_hash` (SHA-256 of the CSV bytes).
- Universe shape used (after explicit verification against `swing/pipeline/runner.py:_step_evaluate`: production's `BatchContext.universe_tickers` is the FULL rs-universe loaded via `load_universe(cfg.paths.rs_universe_path)` — confirmed at D1 by reading runner.py lines 88, 344–350; the parity reconstruction will use the same path with the same `rs_universe_version` and `rs_universe_hash` as recorded on the eval row).
- `current_equity` value used; the formula used to derive it; the production-time equivalent value if it can be reconstructed (read live state from production DB if persisted at run time, else flag as a residual confound and use the closest-in-time-to-the-run reconstruction).
- yfinance cache hit/miss counts during the harness reconstruction.
- Per-tier classification.
- Notes on any tickers excluded from comparison and why (e.g., harness OHLCV fetch failed; production bucket was `error` or `excluded`).

### Run procedure (locked by pre-registration)

1. After D2 lands and tests pass, run the parity module against the auto-selected production `evaluation_run` (most recent with present Finviz CSV) or operator-named run via `--evaluation-run-id N`.
2. Inspect output CSVs WITHOUT computing aggregate agreement rates first: verify the run completed without errors, the manifest is written, the output schema is correct, and the per-ticker rows are well-formed.
3. Compute tier classification per the frozen thresholds in §"Decision tiers."
4. Write the D4 findings doc; do NOT modify D1's pre-registration sections — they are frozen.

### Residual confounds, acknowledged at D1

These are confounds the parity check inherits and cannot eliminate. They are documented here so any near-boundary tier classification can be interpreted in the right frame:

- **OHLCV freshness.** Production fetched OHLCV at production-run-time (2026-04-24 21:07 for eval 15); the parity reconstruction re-fetches at D3-run time. yfinance returns slightly different historical bars depending on when fetched (recent-bar revisions, dividend adjustments, split adjustments). Disagreements driven by bar-value drift on numeric criteria (TT, ADR, RS) are a different class than logic drift; the D4 writeup will characterize the per-criterion disagreement fraction by criterion type to expose this taxonomy.
- **`current_equity` reconstruction approximation.** The production-time value depends on `current_equity(starting_equity, exits, cash_movements)` evaluated at production-run-time. The DB's `trade_exits` and `cash_movements` tables reflect cumulative state, so re-running the formula against today's DB may yield a different value than was used at production-run-time if any rows have been added since. The parity check uses the formula evaluated against today's DB; the manifest records this value AND notes that capital-driven divergences (specifically `risk_feasibility`) are systematically possible even under perfect logic parity.
- **Held-positions reconstruction.** Production includes open-trade tickers in the OHLCV fetch loop and excludes them from evaluation. The set of open trades at D3-run time may differ from production-run-time; this is independent of parity logic but affects which tickers appear in the candidates table on the production side. Since the parity check reads the production-side candidate set directly (rather than re-deriving it), this confound does not affect the comparison set construction; it only affects which tickers were evaluated in the first place. Documented for completeness.
- **Survivorship-bias inheritance.** The harness universe used by the parity reconstruction is current-roster `rs-universe.csv`; if the snapshot has changed since the production run, returns_12w for some tickers may be missing or different. The version+hash recorded on the production eval row is checked against the current rs-universe.csv version+hash; if they differ, the D4 writeup flags the discrepancy explicitly.

---

## Run details (D4 — appended post-D3)

- **Production evaluation_run_id:** 15
- **Production run_ts:** 2026-04-24T21:07:41
- **action_session_date:** 2026-04-25
- **data_asof_date:** 2026-04-24
- **Finviz CSV:** `data/finviz-inbox/finviz24Apr2026.csv` — SHA-256 `4969115f919e3528323c93d3aaf80fdd3315c82466ebcd818339b90354e192a4`
- **Original D3 run (provenance-ambiguous; superseded).** Run timestamp 2026-04-25T06:05:00. `git rev-parse HEAD` returned `59a86c6` (D2 commit) but the working tree already contained the bridge fix `d5b17d0` uncommitted — specifically the `_CountingPriceFetcher` wrapper that produced the `cache_hits=595` value. The original manifest's `harness_git_sha=59a86c6` therefore did not include the working-tree changes the run actually exercised. D5 round-1 adversarial review flagged this as a Major issue.
- **Committed rerun replacing the artifact (canonical D3 output).** Run timestamp 2026-04-25T06:13:55. `git rev-parse HEAD` returned `110f7cc00e7c6527c8698719a21fd57e8aa0b0b3` (the D4 commit, which contains all D2/D3 code plus the bridge fix `d5b17d0`). Outputs are byte-identical to the original run on every bucket/criterion outcome (80/80, 1,440/1,440, 595/0 cache hits/misses); only the manifest's `harness_git_sha` and `harness_run_ts` change. This is the artifact at `research/parity/out/run_20260425_eval_15/`.
- **rs-universe:** version `2026-04-24-1`, hash `bb7b38792ce6170627cfad6299d26efb4514de2ad375cad70617502d3a9d977c`, 516 tickers — **identical** to the values recorded on the production eval row (`universe_match_with_production: true`).
- **`current_equity`:** $7,500. Derivation: `sizing_equity(real_equity=current_equity(starting=$1,200, exits, cash_movements), floor=$7,500) → real=$1,298 sized=$7,500`. Real equity is below the risk floor, so sizing equity = floor. Production-time real-equity is unobserved; any small change in real-equity that does not cross the $7,500 floor is invisible to `risk_feasibility` because sizing equity is clamped above by the floor in both states.
- **OHLCV fetches:** 595 cache hits, 0 cache misses. All bars served from production's parquet cache (`~/swing-data/prices-cache/`). The harness reconstruction explicitly pins `PriceFetcher.get(..., as_of_date=date(2026,4,24))` (the eval row's `data_asof_date` parsed via `_data_asof_to_date`); production calls `as_of_date=None`, which `swing.prices._resolve_asof` then resolves to `last_completed_session(datetime.now())`. The mechanisms differ but the resolved values coincide for this run: `last_completed_session(2026-04-24T21:07:41)` evaluates to `2026-04-24` (Friday, post-NYSE-close), which equals `data_asof_date`. Empirically verified at D5 round-1 adversarial review by direct call to `swing.evaluation.dates.last_completed_session`. Cache key `<ticker>_<lookback>d_asof-2026-04-24.parquet` therefore hits production's bytes for every ticker; yfinance was not contacted during the D3 run. This empirical coincidence does NOT prove the mechanisms are equivalent in general — see §"Caveats and limitations."
- **Tickers compared:** 80. Production candidate set: 81 rows (1 excluded `UCO` ETF/fund-blocklist row, 80 `aplus|watch|skip`). Comparison set excludes the 1 `UCO` excluded-bucket row per D1 §"Comparison primitive."
- **Bucket distribution:** 19 production-`watch` and 61 production-`skip`. Zero production-`aplus` and zero production-`error`.
- **Tickers skipped from comparison at D3 time:** 0.

## Results

| Metric | Numerator | Denominator | Rate |
|---|---:|---:|---:|
| Bucket agreement | 80 | 80 | **100.0000 %** |
| Per-criterion agreement | 1,440 | 1,440 | **100.0000 %** |

Per-bucket transition table:

| Production bucket | Harness bucket | Count |
|---|---|---:|
| watch | watch | 19 |
| skip | skip | 61 |
| (any other transition) | — | 0 |

## Tier classification

Applying D1's frozen thresholds (§"Decision tiers"): bucket agreement 100 % ≥ 99 % AND per-criterion agreement 100 % ≥ 99 % → **Tier 1 — Parity holds.**

The anti-rationalization clause is not load-bearing here: both rates exceed the Tier 1 threshold by the maximum possible margin. There are no near-boundary cases to discuss.

## Disagreement characterization

None. There were zero bucket-level disagreements and zero per-(ticker, criterion) disagreements.

For completeness: across all 18 production criteria (TT1–TT8 in `trend_template`; `prior_trend`, `ma_stack_10_20_50`, `ma_short_rising`, `proximity_20ma`, `adr`, `pullback`, `tightness`, `vcp_volume_contraction`, `orderliness` in `vcp`; `risk_feasibility` in `risk`) for each of 80 tickers, both sides emitted matching `pass`/`fail`/`na` results. Every cell of the 80×18 result matrix matches.

## Findings (descriptive, not prescriptive)

1. **For production evaluation_run 15 with identical reconstructed inputs, harness and production are observationally equivalent classifiers.** Bucket assignment matched on 80 of 80 tickers (100 %); per-(ticker, criterion) `pass`/`fail`/`na` results matched on 1,440 of 1,440 pairs (100 %). The Tier 1 classification meets D1's frozen 99/99 threshold by the maximum possible margin.

2. **The harness's BatchContext universe is byte-faithful to the production run's recorded provenance.** rs-universe version (`2026-04-24-1`) and SHA-256 hash (`bb7b…977c`) on the eval row match the current `reference/rs-universe.csv`; the BatchContext therefore presents identical `universe_tickers` to the harness as production passed at run time. There is no observable parity drift on the universe-shape axis on this run.

3. **No observable equity-axis drift on this run because both states map to the same floor-clamped sizing equity.** What is established empirically is narrower than "current_equity is byte-faithful": the parity reconstruction recomputes equity from the **present** account-DB state via the production formula, not from a persisted production-time value. For eval 15, present real equity ($1,298) is below the risk floor ($7,500), and `sizing_equity` clamps any real-equity below the floor up to the floor. Both production-run-time and D3-reconstruction-time real-equity values are therefore mapped to the same floor-clamped $7,500, **regardless of any within-floor drift** between the two times. The `risk_feasibility` criterion sees identical inputs on both sides because of this masking, not because the underlying real-equity values are demonstrably equal. A future run where present real equity has moved above the floor would un-mask any production-vs-reconstruction-time real-equity drift; eval 15 does not exercise that path.

4. **OHLCV freshness was not a residual confound for this run.** All 595 PriceFetcher requests served from the on-disk parquet cache; zero cache misses, zero yfinance contacts. The harness reconstruction passes `as_of_date=date(2026,4,24)` (the eval row's `data_asof_date`); production used `as_of_date=None` which `_resolve_asof` mapped to `last_completed_session(2026-04-24T21:07:41) = 2026-04-24`. The two mechanisms produced the same cache key for this run, so the harness consumed the same bytes production consumed. Any per-criterion disagreement that could plausibly arise from yfinance recent-bar revisions or dividend/split adjustments did not have an opportunity to manifest on this run. The mechanism-vs-value coincidence is recorded as a caveat: cache-key coincidence is not mechanism equivalence.

5. **The candidate-sparsity diagnostic's residual ~50× rate gap is not explained by harness-vs-production parity drift on this single-run sample.** The diagnostic measured Russell-3000-5× at 0.00977 % per ticker-day vs the Session 2a anchor of ~0.500 %. With Tier 1 parity on this run, candidates 1 (Finviz pre-screening), 2 (time-period regime), and the Session 2a anchor's broad Wilson CI (consistent with true rates as low as 0.05 %) remain the named explanations for the residual gap. **This finding does not establish that parity holds globally** — see §"What this study does NOT say."

6. **The parity reconstruction's faithfulness to `_step_evaluate` is itself audited by the 100 % agreement on this run.** A divergence in `BatchContext` shape, `current_equity` derivation, or OHLCV slicing would generically show up as systematic per-criterion disagreement (especially on `TT8_rs_rank` for universe drift, on `risk_feasibility` for equity drift, and on TT1–TT7 for OHLCV drift). The empirical 0/1,440 disagreement rate is consistent with the reconstruction being faithful for this input set; it is not a proof of faithfulness for inputs not exercised by this run, and specifically does not exercise the floor-cross or universe-membership-fallback branches called out in Findings 3 and §"Caveats and limitations."

7. **Eval 15 is a "no-A+" run.** Production produced 0 A+ signals on 2026-04-24. The surfaces explicitly NOT compared (entry_target / initial_stop / pivot rounding) therefore did not bind on this run. A future run with one or more A+ candidates would exercise that comparison surface; this run does not.

## What this study does NOT say

- This study does **NOT** establish parity globally. n = 1 production run, 80 tickers, 1,440 per-criterion pairs. The Tier 1 classification on this sample is descriptive of THIS run's inputs only. The named follow-on for tighter inference is multi-run characterization across a broader window of production runs (e.g., the 8 most-recent runs in `evaluation_runs`); that follow-on is out-of-scope here.
- This study does **NOT** test alternative explanations for the candidate-sparsity diagnostic's residual ~50× rate gap. Hypotheses 4 (time-period regime), 6 (Finviz universe reconstruction), and Session 2a anchor noise are still on the table after this study.
- This study does **NOT** recommend any production-code change. Tier 1 means "parity holds on this run"; it is not an endorsement of any specific production code path. Conversely, it is not a verdict that the harness is correct in any deeper sense — only that harness and production agree on this run.
- This study does **NOT** test the harness's behavior on tickers that production's `_step_evaluate` placed in `bucket = excluded` or `bucket = error`. By the D1 §"Comparison primitive," those rows are out of comparison scope.
- This study does **NOT** verify that the parity reconstruction would faithfully mirror production under conditions that were not exercised on this run — e.g., a run where the Finviz CSV contains tickers absent from `rs-universe.csv` (would route through `compute_rs`'s `fallback_spy` branch); a run with a held-position ticker that would otherwise be excluded; a run where `as_of_date` resolves to a different session than `data_asof_date`. These untested branches are listed as caveats, not as known-broken paths.
- This study does **NOT** test parity at the granularity of `Candidate.pivot`, `Candidate.initial_stop`, `Candidate.adr_pct`, `Candidate.rs_rank` numerics. The D1 §"Surfaces explicitly NOT compared" excludes these by design (production rounds; harness retains floats).

## Caveats and limitations

- **Single-run sample size.** As named in D1 §"Sample-size limitation," 80 tickers × 18 criteria = 1,440 per-criterion pairs is at the upper end of the brief's anticipated 420–700 range, but is small in absolute terms. The classification rests on this single sample.
- **No A+ candidates on the run.** Eval 15 had zero A+ outcomes. The A+-only fields (`pivot`, `initial_stop`, `next_earnings`) and any production-vs-harness rounding semantics on those fields were not exercised. A follow-on run on a date with A+ activity would tighten this caveat.
- **OHLCV freshness residual is dormant on this run, not eliminated as a class.** Production's parquet cache for `as_of_date=2026-04-24` was already populated at production-run time and the parity reconstruction read it cold. A run where some tickers are NOT cache-hit (e.g., a finviz CSV that introduces a brand-new ticker post-production) would re-fetch via yfinance and could exhibit recent-bar drift. The 0-cache-miss outcome here is an empirical observation, not a structural invariant.
- **`as_of_date` mechanism differs between harness reconstruction and production.** Production calls `PriceFetcher.get(..., as_of_date=None)` and lets `swing.prices._resolve_asof` map None to `last_completed_session(datetime.now())` BEFORE the fetch — that resolved value is the cache key. The eval row's `data_asof_date` is then derived AFTER the fetch from the actual fetched OHLCV (`swing/pipeline/runner.py:352–356`: `data_asof = max(df.index.max() for df in ohlcv_by_ticker.values()).date()`). The parity reconstruction explicitly pins `as_of_date=date.fromisoformat(eval_row.data_asof_date)` for both fetch and cache lookup. The natural divergence mode is therefore: yfinance returned bars whose latest date is **earlier** than `last_completed_session(now)` at production-run time (because of holiday gaps, slow data updates, or a ticker whose history ends before the most recent session). In that case production's cache key is keyed to the resolved-`now` session, while the eval row's `data_asof_date` lags it — and the parity reconstruction's cache lookup, pinned to `data_asof_date`, would miss production's cached parquet and either re-fetch or fall through to a different bar set. For eval 15, both values coincided at `2026-04-24` (Friday close, no holiday/lag), so the cache keys and bytes also coincided. The empirical coincidence on this run does not generalize; cache-key coincidence is not mechanism equivalence.
- **`current_equity` reconstruction approximation.** The D1-acknowledged confound did not bite on this run because real equity ($1,298) is below the risk floor ($7,500), so sizing equity is floor-clamped to $7,500 in both production-time and reconstruction-time states. A future run where real equity has moved above the floor would expose any production-vs-reconstruction-time real-equity drift to the comparison.
- **Held-positions reconstruction.** No held-position ticker is in eval 15's `aplus|watch|skip` comparison set (the only excluded ticker, `UCO`, is the configured ETF/fund block, not a held position). Held-position-driven OHLCV-fetch confounds are dormant on this run.
- **Survivorship-bias inheritance.** The harness universe is current-roster `rs-universe.csv`; the parity check inherits the same survivorship profile as the underlying production run. Since the universe matches with full byte-fidelity, no additional survivorship drift was introduced relative to production.
- **Eval 15 is a single date in a single market regime (mid-April 2026, post-Tranche-C-housekeeping).** Findings would not necessarily generalize to other regimes; broader-time-period parity is not within scope.
- **The parity reconstruction itself is new code (`research/parity/` landed in D2 commit `59a86c6`); its faithfulness to `_step_evaluate` is exercised by 31 unit tests on synthetic fixtures plus the empirical 100 % agreement on this run.** Tests covering inputs not exercised here (Finviz tickers absent from rs-universe, held-position ticker overlap, A+ outcomes, NULL `rs_universe_hash` rows, multi-CSV inboxes, etc.) are present in `tests/research/parity/` but the empirical validation surface is necessarily a strict subset of all branches.

## Open questions for the operator

These are open questions the findings might prompt; the study does not answer them. Each is phrased as a question, with no embedded study-design prescription — choice of how (or whether) to follow up is the operator's.

- Does the Tier 1 result on n = 1 run cross the operator's threshold for declaring the harness-vs-production parity-drift hypothesis (hypothesis 5 from the candidate-sparsity diagnostic) NOT to be the dominant residual-gap explanation, or is multi-run characterization (e.g., the 8 most-recent eval rows in the production DB) needed before drawing that inference?
- Given Tier 1 parity, does the operator want to scope hypothesis 6 (Finviz universe reconstruction) next, or hypothesis 4 (time-period regime), or accept Session 2a anchor noise as the residual-gap explanation without further investigation?
- Is a parity run on a date with one or more production A+ candidates worth scheduling, specifically to exercise the `pivot` / `initial_stop` / A+-fields-rounding surface that this run did not exercise?
- Does the operator have a preferred posture on whether the parity comparator's invocation cadence (single-run-on-demand vs periodic) is a question worth answering at all, given that the study's findings do not themselves prescribe one?

## Run artifacts

| File | Contents | Committed |
|---|---|---|
| `research/parity/out/run_20260425_eval_15/run_manifest.json` | Provenance: harness git SHA, eval_run_id, finviz hash, universe match, equity derivation, cache stats, summary counts, tier | yes |
| `research/parity/out/run_20260425_eval_15/parity_table.csv` | One row per ticker (80 rows): prod_bucket, harness_bucket, bucket_match, criterion_total/match_count, per-criterion disagreement summary | yes |
| `research/parity/out/run_20260425_eval_15/summary.csv` | Single-row aggregate + tier | yes |

