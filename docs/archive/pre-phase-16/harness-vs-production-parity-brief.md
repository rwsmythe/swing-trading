# Harness vs Production Parity Check (Hypothesis 5) — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Test hypothesis 5 from the candidate-sparsity diagnostic: "is there silent code drift between the research-branch harness and the production pipeline that would cause the harness to under-count A+ candidates relative to production?" Run a **single-run targeted parity comparison** between the harness's `evaluate_one`-equivalent and production's recorded evaluation for the same inputs, on the most recent production run with a preserved Finviz CSV. Pre-register decision tiers BEFORE viewing data. Descriptive only — no production-code recommendations.
**Expected duration:** ~1 session (3–5 hours).
**Prepared:** 2026-04-25 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions (conventional commits, no-amend, no `--no-verify`, no Claude co-author footer, Phase isolation). Note: research code lives at `research/`, consumes `swing/` read-only.
2. `docs/orchestrator-context.md` — particularly §"Recent decisions and framings" (capital-sensitivity disposition, production-gating-aware-instrumentation pattern, three-branch architecture), §"Anti-patterns to avoid" (vacuous regression tests, mid-session scope expansion, treating "diagnose, don't decide" as soft), §"Lessons captured" (production-gating-mismatch lesson; informational-vs-prescriptive lesson; sample-size-vs-discipline distinction).
3. `research/studies/candidate-sparsity-diagnostic.md` — the immediate predecessor study. §"Findings" point 8 names this study's question; §"What this diagnostic does NOT say" §3 explicitly defers it to hypothesis 5. §"Caveats and limitations" §"Production-vs-replay parity is partial" describes the current parity state.
4. `research/studies/earnings-proximity-exclusion-results.md` — Session 2c evidence summary; sets the discipline pattern (pre-registration commit → run → writeup → adversarial review).
5. `research/harness/earnings_proximity/instrumented_replay.py` — the per-criterion logging wrapper. Your parity primitive will reuse this module's `evaluate_one`-driving pattern.
6. `research/harness/earnings_proximity/replay.py` — the standard replay loop. Note `_slice_up_to`, `_return_12w`, `_MIN_BARS_FOR_EVALUATION`. Your parity primitive must match production's slicing semantics; this module is your reference for how the harness already does it.
7. `swing/pipeline/runner.py` — production's `_step_evaluate`. Read it carefully to understand: (a) what's the BatchContext universe (Finviz tickers vs full rs-universe?); (b) what `current_equity` is passed to `evaluate_one`; (c) what OHLCV is fed in; (d) how `bucket_for` is invoked. Your parity reconstruction must mirror these inputs **exactly** or the parity check measures the wrong thing.
8. `swing/data/migrations/0001_phase1_initial.sql` lines 24–56 — production's `candidates` + `candidate_criteria` table schema. Confirms per-criterion results are persisted; you read them directly via `swing.data.repos.candidates.fetch_candidates_for_run` (which returns Candidates with `criteria` populated).
9. `data/finviz-inbox/` — the preserved Finviz CSVs (Apr 19–24 available as of brief drafting). Verify your target run's CSV is still there before relying on it; the operator may have rotated the inbox.

**Skill posture.**
- DO invoke `superpowers:verification-before-completion` before declaring done.
- DO invoke `copowers:adversarial-critic` after the findings-writeup commit lands. Standing convention; iterate to `NO_NEW_CRITICAL_MAJOR`. Adversarial review here matters MORE than usual because the parity check's instrumentation is new and could itself be biased (cf. candidate-sparsity diagnostic R1 Critical caught production-gating mismatch in instrumentation).
- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans` — scope is fully specified by this brief.

---

## 1. Strategic context (compressed)

The candidate-sparsity diagnostic (Tranche C, 2026-04-25) measured A+ rate per ticker-day across 4 universe×capital cells:

| Cell | Rate per ticker-day |
|---|---|
| SPX+NDX 1× ($7,500) | 0.00193% |
| SPX+NDX 5× ($37,500) | 0.00387% |
| Russell 3000 1× | 0.00890% |
| Russell 3000 5× | 0.00977% |
| **Production observation (Session 2a anchor)** | **~0.500%** (n=2/400) |

The most-permissive matrix cell (Russell 3000 5×) reaches ~50× below the production observation. Universe + capital scaling combined explained <2.5× of that gap. The residual ~50× is **unexplained** by the variables the diagnostic varied. Three named candidates for the residual (per diagnostic §"Findings" point 8):

1. **Finviz pre-screening** — production starts from operator's Finviz CSV (a curated subset); harness starts from a broader universe (rs-universe.csv or IWV).
2. **Time-period regime** — diagnostic ran 2024-04 → 2026-04; production observation was from a recent window (Session 2a).
3. **Harness-vs-production parity drift** — silent code/plumbing differences between the research-branch reuse of `swing.evaluation` and the production pipeline's wiring.

**This study scopes to #3.** If parity is high, the residual gap is attributable to #1 + #2 (or to anchor noise: Session 2a's CI [0.137%, 1.806%] is consistent with true rates as low as 0.05%). If parity is low, drift is a meaningful explanation and warrants either (a) a harness fix or (b) hypothesis 6 (Finviz universe reconstruction) to rule out the universe-selection contribution.

This study does NOT test hypothesis 6 (Finviz reconstruction) or hypothesis 4 (regime). It is a single-question scope: **for identical inputs, do harness and production produce identical buckets and per-criterion results?**

---

## 2. Scope — single-run targeted comparison

### In scope

- Build a parity-comparison module under `research/parity/` (new directory). The module:
  - Selects the comparison run automatically (most recent production `evaluation_runs` row whose `finviz_csv_path` references a still-present file in `data/finviz-inbox/`). Allow override via CLI flag `--evaluation-run-id <N>`.
  - Reads production's per-(ticker, criterion) results from the DB (read-only).
  - Reconstructs the harness inputs to mirror production exactly for that run: same universe (verify shape from §0 read of `_step_evaluate`), same date, same `current_equity` (derive identically to production), same OHLCV (re-fetch with yfinance; cache hits expected for tickers already in the research cache).
  - Runs `evaluate_one` per ticker for the production date.
  - Emits a parity table CSV (one row per ticker; columns: ticker, prod_bucket, harness_bucket, bucket_match, per_criterion_match_count, per_criterion_total, per_criterion_disagreements_summary).
  - Emits a summary CSV (overall agreement counts + the Tier classification per §4).
  - Emits a run manifest JSON (provenance: harness git SHA, production evaluation_run_id, finviz CSV path + hash, capital, universe shape, cache stats, per-tier classification).
- Pre-registration commit (D1) — the study doc with frozen thresholds, BEFORE running data. Use the discipline established in `research/studies/earnings-proximity-exclusion-results.md`.
- Implementation commit (D2) — the parity module + tests on synthetic fixtures.
- Run commit (D3) — the actual parity-comparison artifacts.
- Findings writeup commit (D4) — `research/studies/harness-vs-production-parity.md` with results and tier classification.
- Adversarial-review fix commits (D5+) as needed.

### Out of scope

- Multi-run characterization. If the single-run check shows perfect parity, the n=1 limitation is documented; no expansion. If it shows divergence, the divergence is characterized but expansion to multi-run is a SEPARATE follow-on session.
- Hypothesis 6 (Finviz universe reconstruction).
- Hypothesis 4 (time-period regime).
- Any production-code change (Phase 2 carve-out NOT granted).
- Any prescription. This study is descriptive: it reports the parity tier and the divergence characterization; it does NOT recommend "fix the harness this way" or "production should change." Findings → "open questions"; not "recommended actions."
- yfinance OHLCV freshness reconciliation. The harness re-fetches OHLCV at study-run time; production fetched at production-run time. Tiny differences (recent-bar adjustments, dividends, splits) are an inherent residual confound. Document but do not attempt to eliminate.
- Earnings handling. Production does not apply earnings filtering in `bucket_for` (earnings-proximity exclusion was research-branch experimental, deferred per Session 2c). The harness's `instrumented_replay` produces evaluations regardless of earnings (earnings only annotates A+ signals). No earnings handling needed for the parity check.
- Performance optimization. ~30–50 tickers in a typical Finviz CSV; comparison runtime is negligible.

---

## 3. Binding conventions

- **Branch:** `main`. No feature branch.
- **Commits:** conventional. **No Claude co-author footer. No `--no-verify`. No amending.**
- **TDD:** failing test first → see fail → minimal implementation → see pass → commit, per logical change.
- **Tests:** `python -m pytest -m "not slow" -q` must stay green. Current baseline 721 passing on `main` (per `25a796e`). Your new tests under `tests/research/parity/` should add to this count.
- **Phase isolation:** Touch `research/` only. No carve-out for `swing/`. Read `swing/` modules; do not modify them.
- **Pre-registration discipline:** D1 commit (study doc with thresholds) MUST land BEFORE D3 (data run). The git history must show this ordering for the study to be honestly pre-registered. Anti-rationalization clause: thresholds in D1 will not be modified post-data; D5 adversarial-review fixes can clarify framing but cannot move tier boundaries.

---

## 4. Pre-registration (D1)

Create `research/studies/harness-vs-production-parity.md`. Commit with message `docs(research): pre-registration commit — harness-vs-production parity check`. The pre-registration MUST contain:

### Hypothesis statement

> The full harness pipeline (universe loading + RS computation + OHLCV slicing + `evaluate_one` + bucket assignment) produces identical bucket assignments and identical per-criterion `pass/fail/na` results as production's `_step_evaluate`, when fed identical inputs (same universe, same date, same current_equity, same OHLCV).

### Comparison primitive

For one production evaluation_run R:
- Production side: `fetch_candidates_for_run(conn, R)` returns Candidates with bucket and per-criterion results.
- Harness side: for each ticker T in R's candidate set, run `evaluate_one(CandidateContext(...))` with reconstructed inputs.
- Comparison: per-ticker `prod_bucket == harness_bucket` (bucket parity); per-(ticker, criterion) `prod_result == harness_result` for every criterion present in either side (per-criterion parity).

### Decision tiers (frozen pre-data)

Computed across all tickers in the comparison run R.

- **Tier 1 — Parity holds.** Bucket agreement ≥99% AND per-criterion agreement ≥99% (where per-criterion agreement is `matching_pairs / total_pairs` over all (ticker, criterion) tuples, with mismatched-presence counted as disagreement). Interpretation: harness and production are equivalent classifiers for this run's inputs. The residual ~50× rate gap must be attributable to (a) Finviz pre-screening, (b) time-period regime, (c) Session 2a anchor noise (its CI is consistent with true rates as low as 0.05%), or (d) some unidentified factor outside the parity scope.

- **Tier 2 — Minor drift.** 95% ≤ bucket agreement < 99% OR 95% ≤ per-criterion agreement < 99%. Interpretation: drift exists but is unlikely to dominate the rate gap. Characterize the divergent surfaces; do not act in this study.

- **Tier 3 — Drift-dominant.** Bucket agreement < 95% OR per-criterion agreement < 95%. Interpretation: drift plausibly explains a meaningful fraction of the residual rate gap. Warrants follow-on: either harness fix (if production is correct) or production audit (if harness's logic is in fact correct). Tier 3 does NOT in itself recommend either fix; it triggers a separate scoping conversation with the operator.

### Anti-rationalization clause

The tier boundaries (99/95) are frozen at D1. If post-data results sit near a boundary (e.g., 98.7% per-criterion agreement), the result IS Tier 2; no boundary adjustment to push it into Tier 1. Findings writeup may discuss the proximity but the classification is what it is.

### Sample-size limitation

A single production run typically has ~30–50 tickers per Finviz CSV. With ~14 criteria per ticker, the per-criterion sample is ~420–700 pairs. This is small. The study's tier classification on this sample is descriptive of THIS RUN; it does NOT establish parity (or non-parity) globally. Multi-run characterization is the named follow-on if the operator wants tighter inference.

### Surfaces explicitly NOT compared

These are out of comparison scope (their divergence is a known harness-vs-production design difference, not "drift"):

- A+ signal entry_target / initial_stop / pivot — production rounds and stores these to DB columns (`pivot`, `initial_stop` REAL); harness retains floats. Compare by tolerance, not equality, OR exclude from the parity assertion.
- Evaluation timestamp; harness uses `now`, production used pipeline-run-time.
- `notes` field on Candidate; production may set ticker-specific notes (e.g., `'open position'` for excluded tickers).
- Bucket `error` — production may set bucket=`error` for tickers that raised exceptions during evaluation; harness re-runs may not encounter the same transient failures.

### Provenance commitments

The D3 run manifest will record:
- Harness git SHA (post-D2 commit).
- Production evaluation_run_id, action_session_date, finviz_csv_path, finviz_csv_hash (SHA-256 of the CSV bytes).
- Universe shape used (after §0 read of `_step_evaluate`: confirm whether BatchContext universe is the Finviz subset or the full rs-universe; record which).
- `current_equity` value used; the formula used to derive it; the production-time equivalent value (read from production DB if persisted, else flag as a residual confound).
- yfinance cache hit/miss counts.
- Per-tier classification.
- Notes on any tickers excluded from comparison and why.

### Run procedure (locked by pre-registration)

1. After D2 lands and tests pass, run the parity module against the auto-selected (or operator-named) production evaluation_run.
2. Inspect output CSVs WITHOUT looking at agreement rates first — verify the run completed without errors, manifest is written, output schema is correct.
3. Compute tier classification per the frozen thresholds.
4. Write D4 findings doc; do NOT modify D1 thresholds.

---

## 5. Implementation (D2)

### 5.1 Module layout

```
research/
  parity/
    __init__.py
    fetcher.py        # production-DB read; harness-input reconstruction
    comparator.py     # bucket + per-criterion comparison primitive
    run.py            # CLI entrypoint
tests/
  research/
    parity/
      __init__.py
      test_fetcher.py
      test_comparator.py
      test_run_smoke.py
```

**No edits** to `research/harness/earnings_proximity/`. The parity check imports from there (e.g., `_slice_up_to`, `_return_12w`) but does not modify it.

### 5.2 `comparator.py` — the comparison primitive

```python
@dataclass(frozen=True)
class CriterionDisagreement:
    criterion_name: str
    prod_result: str | None  # None if criterion absent on prod side
    harness_result: str | None  # None if criterion absent on harness side
    prod_value: str | None
    harness_value: str | None

@dataclass(frozen=True)
class TickerParity:
    ticker: str
    prod_bucket: str | None  # None if ticker absent in production
    harness_bucket: str | None  # None if ticker absent in harness
    bucket_match: bool
    criterion_disagreements: tuple[CriterionDisagreement, ...]
    criterion_total_compared: int  # union of criteria present in both sides
    criterion_match_count: int

def compare(prod_candidate: Candidate | None, harness_candidate: Candidate | None) -> TickerParity:
    ...
```

Test on synthetic fixtures: identical → bucket_match=True, no disagreements; one criterion differs → exactly one disagreement; bucket differs but criteria identical → bucket_match=False, no per-criterion disagreements; ticker absent on one side → bucket=None on that side.

### 5.3 `fetcher.py` — production read + harness reconstruction

Two functions:

```python
def fetch_production(
    conn: sqlite3.Connection,
    evaluation_run_id: int,
) -> dict[str, Candidate]:
    """Returns candidate by ticker for the run, with criteria populated."""

def reconstruct_harness_inputs(
    *,
    conn: sqlite3.Connection,
    evaluation_run_id: int,
    cache_dir: Path,
    config: Config,
) -> HarnessInputs:
    """Builds the BatchContext, MarketContext, current_equity,
    and per-ticker OHLCV slices that the harness's evaluate_one needs.

    The BatchContext universe must mirror production exactly. Verify in
    swing/pipeline/runner.py:_step_evaluate which is in use:
    - If production's BatchContext universe is the Finviz subset: use the
      ingested-ticker set (`SELECT DISTINCT ticker FROM candidates WHERE
      evaluation_run_id = R`).
    - If production's BatchContext universe is the full rs-universe.csv:
      use load_universe(rs_universe_csv).tickers.
    Document the resolved choice in the manifest.

    current_equity must mirror production exactly. Re-derive using the
    same path swing.pipeline.runner._step_evaluate uses (read it; do not
    guess). Likely candidates: cfg.account.starting_equity, or
    swing.trades.equity.sizing_equity(...). If production reads live
    cash + realized P&L, that path may have moved since the production
    run; use the closest-in-time-to-the-run reconstruction or flag the
    residual confound in the manifest.
    """
```

Tests with sqlite in-memory DB: insert known candidates + criteria for a fake evaluation_run; assert fetch_production returns them correctly. Tests with synthetic config + fake yfinance cache: assert reconstruct_harness_inputs builds inputs matching the expected shape.

### 5.4 `run.py` — CLI entrypoint

```bash
python -m research.parity.run \
    --output-dir research/parity/out/run_<DATE>_eval_<N>/ \
    [--evaluation-run-id N]   # default: most recent with present finviz CSV
    [--cache-dir <path>]      # default: ~/swing-data/research-cache/
```

CLI:
1. Auto-select evaluation_run_id if not provided.
2. Connect to production DB at `cfg.paths.db_path`.
3. Fetch production candidates + reconstruct harness inputs.
4. For each ticker in the union of {prod tickers, harness universe}, run `evaluate_one` on harness side.
5. Compare.
6. Write outputs (parity_table.csv, summary.csv, run_manifest.json).
7. Print summary + tier classification to stdout.

Smoke test: with a fake DB pre-populated and a fake yfinance cache pre-populated, the CLI runs end-to-end and emits expected files. No real production data needed for the smoke; that's D3.

### 5.5 Test discipline

- `test_comparator.py`: ~6–10 cases covering the disagreement permutations enumerated in §5.2.
- `test_fetcher.py`: 2–4 cases for `fetch_production` (basic; missing run; multi-criterion); 2–3 cases for `reconstruct_harness_inputs` (mocked yfinance, mocked config).
- `test_run_smoke.py`: end-to-end with an in-memory DB + monkeypatched yfinance fetch returning canned dataframes. Asserts CSV outputs match expected schema; manifest contains expected fields.

Total expected new tests: ~12–15. Fast suite should grow from 721 to 733–736.

### 5.6 Implementation commit shape

Commit body:
```
feat(research): harness-vs-production parity comparator (D2)

Module under research/parity/ that compares production's persisted
per-criterion evaluation results against harness `evaluate_one`
output for the same inputs. Pre-registration discipline established
in research/studies/harness-vs-production-parity.md (D1).

Comparator: per-(ticker, criterion) result matching with explicit
disagreement records. Reconstruction: builds harness inputs (universe,
current_equity, OHLCV slices) to mirror production exactly per
swing/pipeline/runner.py:_step_evaluate. CLI auto-selects most-recent
production run with present Finviz CSV; --evaluation-run-id override.

Tests on synthetic fixtures only; D3 will run on real production data.

Phase isolation: research/ only. No swing/ modifications.
```

---

## 6. Run (D3)

After D2 lands and tests pass:

1. Verify your target evaluation_run exists in the production DB. Connect read-only:
   ```bash
   sqlite3 ~/swing-data/swing.db "SELECT id, run_ts, data_asof_date, finviz_csv_path FROM evaluation_runs ORDER BY run_ts DESC LIMIT 5"
   ```
2. Verify the Finviz CSV is still in `data/finviz-inbox/`.
3. Verify yfinance cache covers the tickers (research cache at `~/swing-data/research-cache/`). Any missing OHLCV tickers will fetch fresh; this is fine for a single small Finviz universe.
4. Run the parity comparator:
   ```bash
   python -m research.parity.run \
       --output-dir research/parity/out/run_$(date +%Y%m%d)_eval_<N>/
   ```
5. Inspect output structure (file listing, manifest content, parity_table schema). Do NOT compute or interpret tier classification yet; that's D4.
6. Commit the run artifacts:
   ```
   data(research): parity comparator run (D3) — eval_<N>, <DATE>

   Run output for the harness-vs-production parity check on production
   evaluation_run <N> (action_session <DATE>; finviz CSV finviz<DDMmmYYYY>.csv).
   Pre-registration: research/studies/harness-vs-production-parity.md (D1).

   Tier classification deferred to D4 findings doc.
   ```

`evaluations.csv`-style large files MUST be in `.gitignore` if size warrants. Smaller artifacts (manifest, summary, parity table) commit. Use the same gitignore convention as `research/harness/earnings_proximity/diagnostic-out/`.

---

## 7. Findings writeup (D4)

Update `research/studies/harness-vs-production-parity.md`. Append (do NOT modify D1's pre-registration sections — they are frozen):

- §"Run details" — production evaluation_run_id, date, finviz CSV, ticker count, harness git SHA, capital used.
- §"Results" — bucket agreement count + rate; per-criterion agreement count + rate; disagreement summary tables.
- §"Tier classification" — apply D1's frozen thresholds; state the resulting tier directly.
- §"Disagreement characterization" (if any) — for each ticker with bucket mismatch, the criterion(s) that diverged and the prod-vs-harness values for each. For per-criterion disagreements that don't change the bucket, summary by criterion name.
- §"Findings (descriptive, not prescriptive)" — 3–6 numbered findings; mirror the descriptive style of `research/studies/candidate-sparsity-diagnostic.md` §"Findings."
- §"What this study does NOT say" — at minimum: does not establish parity globally (n=1 run); does not test alternative residual-gap explanations (Finviz pre-screening, regime, anchor noise); does not recommend production or harness changes.
- §"Caveats and limitations" — at minimum: single-run sample; OHLCV freshness residual; current_equity reconstruction approximation; survivorship-bias inheritance from the harness universe.
- §"Open questions for the operator" — phrased as questions, not recommendations. Examples: "Does the tier classification cross the operator's threshold for follow-on multi-run characterization?"; "If Tier 2 or 3 is reached, which divergence is most informative — per-criterion or bucket — for scoping a follow-on?"; "If Tier 1, does the operator want to pursue hypothesis 6 (Finviz universe reconstruction) or accept anchor noise + universe selection as the residual-gap explanation?"

Commit:
```
docs(research): harness-vs-production parity findings (D4)

Tier <N> result on production evaluation_run <X>. <Headline summary
of bucket and per-criterion agreement rates>. Findings descriptive
only; open questions to operator.
```

---

## 8. Adversarial review (D5+)

After D4 lands, invoke `copowers:adversarial-critic` on the combined diff (D2 + D3 + D4). Iterate to `NO_NEW_CRITICAL_MAJOR`. **Specific watch items** (paste these into your invocation):

- **Production-vs-instrumentation-parity verification.** The production-gating-mismatch lesson from candidate-sparsity diagnostic R1 Critical applies analogously here: does `reconstruct_harness_inputs` actually mirror production's `_step_evaluate`? Trace through `_step_evaluate` line-by-line and verify each input (universe shape, current_equity derivation, OHLCV slicing semantics, MarketContext fields) matches. Any divergence is itself "drift" — the parity check would systematically over- or under-report agreement.
- **`current_equity` derivation.** Production's value at the production-run-time may differ from the value any reconstruction can produce now (live cash + realized P&L state has moved). If your reconstruction can only approximate, the manifest must clearly say so AND the tier interpretation must acknowledge that capital-driven divergences (specifically `risk_feasibility` results) are systematically possible even under perfect parity.
- **Universe shape.** If production uses Finviz subset for BatchContext but harness uses full rs-universe (or vice versa), every ticker's `rs_rank` and `rs_return_12w_vs_spy` will diverge — and `TT8_rs_rank` is in the trend_template. This single misalignment could swing per-criterion agreement by tens of percentage points. Verify exhaustively.
- **OHLCV freshness.** yfinance returns slightly different historical bars depending on when fetched (recent-bar revisions, dividend adjustments). The parity check inherits this. Disagreements driven by bar-value drift (vs logic drift) are a different class. Where feasible, characterize: of the per-criterion disagreements, what fraction map to a numeric criterion (TT, ADR, RS) where bar-value drift would plausibly cause a flip vs to a structural criterion (`risk_feasibility`, VCP) where it wouldn't? This is a useful taxonomy regardless of tier.
- **Pre-registration honesty.** Verify the D1 commit landed BEFORE D3 in `git log`. If accidentally interleaved, the discipline is broken; the writeup must acknowledge this.
- **Sample-size framing.** The findings writeup must not over-claim. ~30–50 tickers from one run is descriptive of one run, not of the harness-vs-production system globally. Verify the writeup frames findings appropriately.
- **Anti-rationalization compliance.** Verify D4's tier classification used D1's exact thresholds, with no language that effectively shifts a near-boundary case.
- **Descriptive-not-prescriptive compliance.** Search the writeup for words like "should," "recommend," "must" used as prescriptive direction. Each instance is a candidate violation; reframe as descriptive or move to the open-questions section.

Fix any major-severity findings in NEW commits per no-amend rule. Minor findings either fix in same follow-up or `ACCEPT-with-rationale`.

---

## 9. Done criteria

- D1 commit (pre-registration) landed BEFORE D3 (run). `git log` order verifies.
- D2 commit (implementation + tests) landed; tests pass.
- D3 commit (run artifacts) landed; manifest + parity_table + summary present.
- D4 commit (findings writeup) landed; tier classification applied to D1's frozen thresholds.
- D5+ adversarial-review pass landed (separate commit per fix, no amend); verdict `NO_NEW_CRITICAL_MAJOR`.
- Fast suite green: 733+ passing (721 baseline + ~12+ new tests).
- No `swing/` modifications. No production DB modifications.
- Return report produced per §10.

---

## 10. Return report format

```
## Harness-vs-production parity check — return report

### Commits landed
- <SHA1> docs(research): pre-registration commit — harness-vs-production parity check (D1)
- <SHA2> feat(research): harness-vs-production parity comparator (D2)
- <SHA3> data(research): parity comparator run (D3)
- <SHA4> docs(research): harness-vs-production parity findings (D4)
- <SHA5+> (if any) fix(research): address adversarial review finding(s)

### Run details
- Production evaluation_run_id: <N>
- Action session: <YYYY-MM-DD>
- Finviz CSV: <filename>; SHA-256: <hash>
- Tickers compared: <count>
- Capital used: $<amount>; derivation method: <description>
- Harness git SHA at run: <SHA>

### Results
- Bucket agreement: <count>/<total> = <rate>%
- Per-criterion agreement: <count>/<total> = <rate>%
- Tier classification: <Tier 1 | Tier 2 | Tier 3>

### Disagreement summary (if any)
- Bucket-level: <list of (ticker, prod_bucket, harness_bucket) tuples>
- Per-criterion: <summary by criterion name with counts>

### Tests
- Before: 721 passing (baseline from 25a796e)
- After: <N> passing, 0 failing. New tests: <count>.

### Adversarial review verdict
- <NO_NEW_CRITICAL_MAJOR | findings summary if any>

### Deviations from brief
- <Empty if none. List any judgment calls and their rationale, especially for ambiguities in `_step_evaluate` reconstruction.>

### Open questions for orchestrator
- <Empty if none.>
```

---

## 11. If you get stuck

- **If `_step_evaluate` reconstruction is ambiguous** (e.g., production passes a `current_equity` derived in a way that's hard to reproduce now): document the ambiguity in the manifest, choose the most-faithful approximation, and flag the residual confound. Do NOT silently choose; do NOT block on getting it perfect.
- **If the most recent production run's Finviz CSV has been rotated to `rejected/`** or otherwise removed: try the next-most-recent. If multiple recent runs are missing CSVs, flag in return report and pick the most-recent run that has one. Ideally the operator can re-supply if needed.
- **If yfinance fetches fail for some tickers** during the harness reconstruction: skip those tickers in the comparison (they contribute neither to numerator nor denominator); list them in the manifest. Do not fail the whole run.
- **If parity comes out at exactly Tier 1 with 100% agreement**, the result is still publishable and informative. The writeup should note: "perfect parity on n=1 run; multi-run characterization is the named follow-on for tighter inference; residual ~50× rate gap to production observation is not explained by parity drift on this sample."
- **If parity is much worse than expected (Tier 3 with bucket agreement <50%)**, STOP and re-verify the reconstruction in `_step_evaluate` BEFORE writing up findings. The most-likely explanation for surprising disagreement is reconstruction error, not real harness drift. Double-check universe shape, current_equity, OHLCV slicing semantics. Only when reconstruction is confidently faithful does Tier 3 mean "real drift."
- **If you discover during reconstruction that production's `_step_evaluate` itself uses a research-branch import or other unexpected coupling**: flag in return report with a brief description. This is a different kind of finding than parity drift and is interesting in its own right.
- **If pre-registration discipline is accidentally broken** (e.g., you ran D3 before committing D1): the study is no longer pre-registered. Do not try to hide this; document explicitly in the writeup that D1's "pre-registration" was post-hoc. The operator can decide whether to discard the run and redo, or accept the loss of pre-registration as a study limitation.
