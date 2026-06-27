# Finviz-Pool Per-Criterion Binding-Constraint Analysis — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Characterize where production loses A+ candidates between the operator's Finviz-pool input and final A+ classification. Aggregate the per-criterion production-gated blocker distribution across all production evaluation_runs whose Finviz CSVs are still on disk; compute watch:A+ ratio; identify the "near-A+ defensible" subset (watch-bucket tickers whose only non-pass criteria are in a frozen doctrine-defensible miss set). Pure SQL/DataFrame aggregation on existing production DB data — no yfinance, no harness re-run, no universe loaders. Pre-register analytical structure BEFORE running. Descriptive only — no production-code recommendations.
**Expected duration:** ~1 session (3–4 hours).
**Prepared:** 2026-04-25 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions (conventional commits, no-amend, no `--no-verify`, no Claude co-author footer, Phase isolation). Note: research code lives at `research/`; consumes `swing/` read-only.
2. `docs/orchestrator-context.md` — particularly §"Recent decisions and framings" (framework framing 2026-04-25, evidence gap framing, sub-A+ trading is operator's actual practice), §"Anti-patterns to avoid" (vacuous tests, mid-session scope expansion, doctrinal vs evidence framing).
3. `research/studies/candidate-sparsity-diagnostic.md` — the predecessor study. Sources the production-gated blocker methodology you'll reuse. §"Two metrics for the binding-constraint analysis" — production-gated is the primary metric per R1 Critical lesson.
4. `research/harness/earnings_proximity/scripts/recompute_binding_prod_gated.py` — the production-gated blocker computation. **Reuse this directly; do not reimplement.** Its logic is canonical for "what would production's `bucket_for` reject this candidate for, in production gating order."
5. `swing/data/migrations/0001_phase1_initial.sql` lines 24–56 — `candidates` + `candidate_criteria` schema. Confirms per-(ticker, criterion) `pass`/`fail`/`na` results are persisted.
6. `swing/data/repos/candidates.py` — the existing `fetch_candidates_for_run` returns Candidates with `criteria` populated. Reuse for production reads.
7. `swing/evaluation/scoring.py` and the existing `bucket_for` function — verify the production gating order being mirrored. (Do not modify.)
8. `data/finviz-inbox/` — preserved Finviz CSV files. The study restricts attention to evaluation_runs whose `finviz_csv_path` resolves to a present file here.

**Skill posture.**
- DO invoke `superpowers:verification-before-completion` before declaring done.
- DO invoke `copowers:adversarial-critic` after the findings-writeup commit lands. Standing convention; iterate to `NO_NEW_CRITICAL_MAJOR`. Watch items: production-gating mismatch (the recurring class of finding), doctrinal-defensible-set frozen-at-D1 compliance, descriptive-not-prescriptive compliance.
- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans` — scope is fully specified by this brief.

---

## 1. Strategic context (compressed)

The operator's question, in framework terms: "I see ~2 A+/year from production. Why? Where do the ~50 daily Finviz tickers go? What's the watch bucket actually doing? Are there 'near-A+' watch tickers where the missing criterion is doctrine-defensible (would justify trading at smaller size or after re-evaluation), vs missing criteria that mean 'the setup doesn't exist yet'?"

The data needed already exists. Production persists per-(ticker, criterion) results in `candidate_criteria`. Every Finviz CSV the operator has ingested has produced an `evaluation_runs` row + per-ticker rows in `candidates` + per-criterion rows in `candidate_criteria`. The candidate-sparsity diagnostic ran this analysis on broad universes (SPX+NDX, Russell 3000); the harness-vs-production parity check verified harness↔production agreement on n=80 from one run. **Neither study aggregated the per-criterion data on the operator's actual Finviz-pool input.** This study fills that gap.

**Operator-stance context (settled per orchestrator-context.md 2026-04-25):**

- Doctrine of "only A+" is a known prior; operator is willing to accept that absolute framing is too conservative when justified by evidence.
- Sub-A+ trading is in actual practice (VIS trade, framework-recommended at TT + price threshold).
- Hypothesis-tagged sub-optimal trades are acceptable as cost-of-development to generate evidence (parallel Phase 3e change adds the labeling infrastructure).

This study's near-A+ defensible subset finding becomes operationally actionable in that context — it's the candidate list of "doctrine-defensible misses worth experimenting with" for hypothesis-tagged trade evidence collection.

---

## 2. Scope

### In scope

- Build a Finviz-pool aggregation module under `research/finviz_pool_analysis/` (new directory). The module:
  - Identifies all production evaluation_runs whose `finviz_csv_path` points to a still-present file in `data/finviz-inbox/` (or its `rejected/` subdirectory if relevant).
  - For each such run, reads candidates + per-criterion results from production DB (read-only).
  - Applies production-gated blocker logic via `recompute_binding_prod_gated.py` (import and reuse — do not reimplement).
  - Aggregates per-criterion blocker counts, bucket distribution, watch:A+ ratio, and near-A+ subset classification per the frozen pre-registration spec.
  - Emits CSV outputs + run manifest.
- Pre-registration commit (D1) — study doc with frozen analytical structure + doctrine-defensible miss set.
- Implementation commit (D2) — the aggregation module + tests on synthetic fixtures.
- Run commit (D3) — the actual aggregation artifacts on production data.
- Findings writeup commit (D4) — `research/studies/finviz-pool-binding-constraints.md` with descriptive results.
- Adversarial-review fix commits (D5+) as needed.

### Out of scope

- Any production-code change (Phase 2 carve-out NOT granted).
- Any prescription. Findings are descriptive: counts, distributions, sample tickers per category. NOT "you should trade these candidates" or "you should change criteria X." → Open-questions section, not recommendations.
- Trade-outcome correlation. The hypothesis-labeling Phase 3e change ships in parallel (separate dispatch); this study does NOT depend on or correlate with trade outcomes. Outcome-by-hypothesis aggregation is a future study once labeled trades accumulate.
- yfinance fetches, harness re-runs, universe loaders. Pure read of existing production DB data.
- Any non-production-gated metric as primary. Per the candidate-sparsity diagnostic R1 Critical lesson, emitted-order blocker counts conflate upstream-rerouted candidates; production-gated is the primary metric. Emitted-order may appear as audit-trail secondary if useful.
- Multi-window or regime-comparison analysis. The study aggregates across whatever production data exists; does not partition by time period.

---

## 3. Binding conventions

- **Branch:** `main`. No feature branch.
- **Commits:** conventional. **No Claude co-author footer. No `--no-verify`. No amending.**
- **TDD:** failing test first → see fail → minimal implementation → see pass → commit, per logical change.
- **Tests:** `python -m pytest -m "not slow" -q` must stay green. **Trust pytest output, not the brief's baseline number** — there is parallel work (hypothesis-labeling Phase 3e change) that may shift the baseline before or during your work. Current baseline is 770 as of `4a372da`; could be 770+N when you start.
- **Phase isolation:** Touch `research/` only. No carve-out for `swing/`. Read `swing/` modules; do not modify them.
- **Pre-registration discipline:** D1 commit (study doc with frozen analytical structure + doctrine-defensible miss set) MUST land BEFORE D3 (data run). Anti-rationalization clause: doctrine-defensible miss set frozen at D1; cannot be modified post-data; D5 adversarial-review fixes can clarify framing but cannot move the set membership.

---

## 4. Pre-registration (D1)

Create `research/studies/finviz-pool-binding-constraints.md`. Commit with message `docs(research): pre-registration commit — Finviz-pool per-criterion binding-constraint analysis`. The pre-registration MUST contain:

### Analytical question

> Across all production evaluation_runs ingested from operator-supplied Finviz CSVs, what is the per-criterion production-gated blocker distribution; what is the watch:A+ bucket ratio; and what fraction of watch-bucket tickers have ONLY doctrine-defensible misses (i.e., are 'near-A+ defensible')?

### Doctrine-defensible miss set (frozen at D1)

The following criteria are designated "doctrine-defensible misses" — failing one of these alone (with all other criteria passing) does not necessarily mean "the setup doesn't exist"; it may instead represent an operationally-tractable circumstance with a doctrine-aligned response:

1. **`TT8_rs_rank`** — already a production `allowed_miss_name`. Listed for completeness; tickers failing only TT8 are A+ classified by production today.
2. **`risk_feasibility`** — capital-blocked; doctrine-aligned response is "smaller position than standard, OR pass and revisit at higher capital."
3. **`proximity_20ma`** — timing/extension miss; doctrine-aligned response is "wait for pullback to 20MA, then re-evaluate." Stage-for-re-entry, not trade-anyway.

All other criteria are designated "doctrine-incompatible misses" — failing them means the setup is not present (e.g., VCP not formed; trend not established; prior trend missing). These criteria are: TT1_above_150_200, TT2_150_above_200, TT3_200_rising, TT4_50_above_150_200, TT5_above_50, TT6_above_52w_low_30pct, TT7_within_52w_high_25pct, ma_stack_10_20_50, ma_short_rising, prior_trend, adr, tightness, vcp_volume_contraction, orderliness.

**Anti-rationalization:** the membership of the doctrine-defensible set is FROZEN at D1. Post-data, you may not move criteria in or out of this set. If post-data analysis surfaces a finding like "tickers failing only `adr` look near-A+ in some way," that observation belongs in the open-questions section, NOT as a set-membership change.

### Outputs (required)

For the aggregation across all qualifying evaluation_runs:

1. **Per-criterion production-gated blocker distribution.** Count and % of evaluations blocked by each criterion (per production gating order). Format mirrors candidate-sparsity diagnostic §"Per-criterion binding-constraint analysis."
2. **Bucket distribution.** Counts and % of evaluations falling into each bucket: aplus, watch, skip, error, excluded.
3. **Watch:A+ ratio.** Overall ratio AND per-run ratio (where defined; flag runs with zero A+).
4. **Near-A+ defensible subset.** Count of watch-bucket tickers whose every non-pass criterion is in the doctrine-defensible miss set. Sample 10 tickers (or all if fewer) with: ticker, evaluation_run_id, action_session_date, list of failed criteria.
5. **Near-A+ doctrine-incompatible subset.** Count of watch-bucket tickers that have at least one non-pass criterion OUTSIDE the doctrine-defensible set. Sample 10 (or all if fewer) for visibility — so operator sees what falls into the "not defensible" pool and can sanity-check the boundary.
6. **Number of qualifying evaluation_runs included** (denominator transparency).
7. **Number of evaluation_runs SKIPPED** because their `finviz_csv_path` is no longer on disk; list which.

### Run procedure (locked by pre-registration)

1. After D2 lands and tests pass, run the aggregation against the production DB.
2. Verify outputs are well-formed (CSV schemas; manifest fields). Do NOT interpret yet.
3. Write D4 findings doc applying the frozen analytical structure to the data; do NOT modify D1 sections.

### Sample-size limitation

The number of qualifying evaluation_runs is whatever the operator's production history contains as of the run date. This is NOT a multi-month or regime-balanced sample; it is a snapshot of operator-actual production data to date. Findings are descriptive of THIS snapshot.

### Surfaces explicitly NOT analyzed

- Trade outcomes (handled by separate hypothesis-labeling Phase 3e infrastructure; future correlation study).
- Causal attribution between Finviz filter design and per-criterion blocker patterns (would require counterfactual Finviz-filter variations).
- Comparison to alternative universes (S&P 1500, Russell — handled by other studies).
- Per-sector or per-cap-tier breakdown of binding constraints (out of scope; Finviz pool is small enough that per-sector counts are statistically thin).

### Provenance commitments

The D3 run manifest will record:
- Harness git SHA at run time.
- Production DB path and timestamp of read.
- Number of qualifying evaluation_runs; date range of action_session_date across them.
- Number of total evaluations across all included runs.
- Total candidates read; total `candidate_criteria` rows read.
- Doctrine-defensible miss set membership (frozen, copied verbatim from D1).

---

## 5. Implementation (D2)

### 5.1 Module layout

```
research/
  finviz_pool_analysis/
    __init__.py
    fetcher.py        # production-DB read (qualifying evaluation_runs + candidates + criteria)
    aggregator.py     # blocker distribution, bucket counts, near-A+ classification
    run.py            # CLI entrypoint
tests/
  research/
    finviz_pool/
      __init__.py
      test_fetcher.py
      test_aggregator.py
      test_run_smoke.py
```

### 5.2 `aggregator.py` — analytical primitives

Reuse `recompute_binding_prod_gated.py` for the production-gated blocker computation; do not reimplement. The aggregator owns:

- Bucket counting per qualifying evaluation_run.
- Watch:A+ ratio computation (overall + per-run; handle zero-A+ runs explicitly).
- Near-A+ classification: for each watch-bucket ticker, walk its `candidate_criteria` rows; classify as "defensible" if every non-pass criterion is in the frozen miss set, else "doctrine-incompatible."
- Sample selection: deterministic ordering (e.g., by action_session_date DESC, ticker ASC) for reproducible 10-row samples.

Test on synthetic fixtures: known per-(ticker, criterion) inputs; assert classification is correct; assert bucket counts match; assert near-A+ subset membership is right at the boundary (e.g., ticker failing only TT8+risk_feasibility → defensible; ticker failing TT8+adr → incompatible).

### 5.3 `fetcher.py` — production read

```python
def list_qualifying_evaluation_runs(
    conn: sqlite3.Connection,
    finviz_inbox_dir: Path,
) -> list[QualifyingRun]:
    """Returns evaluation_runs where finviz_csv_path resolves to an existing
    file under finviz_inbox_dir (top level OR rejected/ subdirectory).
    Skipped runs (path missing) are NOT in the returned list but are
    captured in a separate `skipped: list[SkippedRun]` collection for
    manifest reporting.
    """

def fetch_run_candidates_with_criteria(
    conn: sqlite3.Connection,
    evaluation_run_id: int,
) -> list[Candidate]:
    """Reuse swing.data.repos.candidates.fetch_candidates_for_run.
    Verifies criteria are populated."""
```

Tests with sqlite in-memory DB: insert known eval rows + candidates + criteria; assert fetcher returns them correctly; assert path-missing runs are correctly skipped.

### 5.4 `run.py` — CLI entrypoint

```bash
python -m research.finviz_pool_analysis.run \
    --output-dir research/finviz_pool_analysis/out/run_$(date +%Y%m%d)/
```

CLI:
1. Connect read-only to production DB at `cfg.paths.db_path`.
2. List qualifying + skipped evaluation_runs.
3. For each qualifying run, fetch candidates+criteria.
4. Aggregate per pre-registration spec.
5. Write outputs (per_criterion_blockers.csv, bucket_distribution.csv, near_aplus_defensible_sample.csv, near_aplus_incompatible_sample.csv, summary.csv, run_manifest.json).
6. Print summary + bucket counts to stdout (do NOT print interpretation; that's D4).

### 5.5 Test discipline

- `test_fetcher.py`: 4–6 cases (basic; multi-run; path-missing; ordering).
- `test_aggregator.py`: 8–12 cases covering boundary conditions of near-A+ classification (defensible-only set; incompatible-only set; mixed; zero criteria; all-pass; etc.).
- `test_run_smoke.py`: end-to-end with in-memory DB + tmp finviz-inbox; asserts CSV schemas + manifest fields.

Total expected new tests: ~14–20. Fast suite should grow accordingly.

### 5.6 Implementation commit shape

```
feat(research): Finviz-pool binding-constraint aggregator (D2)

Module under research/finviz_pool_analysis/ that aggregates per-criterion
production-gated blocker distribution + bucket counts + watch:A+ ratio +
near-A+ defensible subset classification across all production
evaluation_runs whose Finviz CSVs are present on disk. Reuses
recompute_binding_prod_gated.py for the gating computation.

Pre-registration discipline established in
research/studies/finviz-pool-binding-constraints.md (D1) — including
the frozen doctrine-defensible miss set (TT8_rs_rank, risk_feasibility,
proximity_20ma).

Tests on synthetic fixtures only; D3 will run on real production data.

Phase isolation: research/ only. No swing/ modifications.
```

---

## 6. Run (D3)

After D2 lands and tests pass:

1. Verify the production DB is reachable: `sqlite3 ~/swing-data/swing.db "SELECT COUNT(*) FROM evaluation_runs"` (read-only check).
2. Verify `data/finviz-inbox/` exists and contains expected CSVs.
3. Run the aggregator:
   ```bash
   python -m research.finviz_pool_analysis.run \
       --output-dir research/finviz_pool_analysis/out/run_$(date +%Y%m%d)/
   ```
4. Inspect output structure and manifest. Verify schemas; do NOT interpret.
5. Commit:
   ```
   data(research): Finviz-pool binding-constraint analysis run (D3)

   Run output for the Finviz-pool per-criterion binding-constraint
   analysis. Pre-registration: research/studies/finviz-pool-binding-constraints.md (D1).

   Findings writeup deferred to D4.
   ```

Sample CSVs are small (≤20 rows each); commit them. Per-criterion blocker CSV and bucket distribution CSV are also small. No `.gitignore` additions needed unless the per-(ticker, run) detail file grows large (>1MB; flag if so).

---

## 7. Findings writeup (D4)

Update `research/studies/finviz-pool-binding-constraints.md`. Append (do NOT modify D1 sections — they are frozen):

- §"Run details" — number of qualifying evaluation_runs, date range, total evaluations, harness git SHA, production-DB read timestamp.
- §"Results — bucket distribution" — counts and % per bucket; watch:A+ ratio.
- §"Results — per-criterion production-gated blocker distribution" — full table per the candidate-sparsity diagnostic format.
- §"Results — near-A+ defensible subset" — count, %, sample 10 tickers.
- §"Results — near-A+ doctrine-incompatible subset" — count, %, sample 10 tickers.
- §"Findings (descriptive, not prescriptive)" — 4–8 numbered findings; mirror the descriptive style of `research/studies/candidate-sparsity-diagnostic.md` §"Findings."
- §"What this study does NOT say" — at minimum: does not test trade outcomes; does not recommend criteria changes; does not recommend specific tickers be traded; does not establish whether near-A+ defensible candidates produce edge (that question requires labeled trade outcomes from the parallel Phase 3e infrastructure).
- §"Caveats and limitations" — at minimum: snapshot-of-operator-history sample (not regime-balanced); descriptive of THIS production state (criteria implementation may evolve); doctrine-defensible set membership reflects current 2026-04-25 framework framing.
- §"Open questions for the operator" — phrased as questions, not recommendations. Examples: "Does the near-A+ defensible count cross your threshold for hypothesis-tagged experimental trade-taking?"; "Does the binding-constraint distribution surface any criterion you'd want to investigate at first principles (basic-research candidate)?"; "Is the doctrine-defensible miss set frozen at D1 the right one going forward, or do post-data observations suggest amendment for FUTURE studies (not this one)?"

Commit:
```
docs(research): Finviz-pool binding-constraint findings (D4)

<Headline summary of bucket distribution + binding constraints +
near-A+ defensible subset count>. Findings descriptive only;
open questions to operator.
```

---

## 8. Adversarial review (D5+)

After D4 lands, invoke `copowers:adversarial-critic` on the combined diff (D2 + D3 + D4). Iterate to `NO_NEW_CRITICAL_MAJOR`. **Specific watch items:**

- **Production-gating mismatch (recurring class).** Verify `recompute_binding_prod_gated.py` is being USED, not reimplemented. Verify the production gating order is mirrored exactly. Per candidate-sparsity diagnostic R1 Critical: emitted-order metrics conflate upstream-rerouted candidates and would inflate apparent blocker distribution distortion.
- **Doctrine-defensible set frozen-at-D1 compliance.** Compare D4's set membership to D1's; they MUST be identical. Any post-data movement is a violation.
- **Anti-rationalization compliance.** Search D4 for boundary-shifting language ("just barely," "essentially," "nearly defensible"). Each instance is a candidate violation; reframe.
- **Descriptive-not-prescriptive compliance.** Search for "should," "recommend," "must" used as direction. Reframe or move to open-questions.
- **Manifest integrity.** Verify `harness_git_sha` reflects actual run-time code state, not commit-time. (Parity-check R1 lesson.)
- **Sample-size framing.** Verify writeup does not over-claim from a snapshot-of-operator-history.
- **Path-resolution edge cases.** Verify finviz CSV resolution handles: top-level CSV present; CSV moved to rejected/; CSV deleted; multiple runs pointing to same CSV. Each case is correctly classified (qualifying / skipped / etc.) per D1.

Fix major findings in NEW commits per no-amend rule. Minor findings either fix in same follow-up or `ACCEPT-with-rationale`.

---

## 9. Done criteria

- D1 commit (pre-registration) landed BEFORE D3 (run). `git log` order verifies.
- D2 commit (aggregator + tests) landed; tests pass.
- D3 commit (run artifacts) landed; manifest + per-criterion + bucket + sample CSVs present.
- D4 commit (findings writeup) landed; all sections per §7 present; doctrine-defensible set unchanged from D1.
- D5+ adversarial-review pass landed (separate commits per fix); verdict `NO_NEW_CRITICAL_MAJOR`.
- Fast suite green: trust pytest output (baseline drift expected from parallel work).
- No `swing/` modifications. No production DB modifications.
- Return report produced per §10.

---

## 10. Return report format

```
## Finviz-pool binding-constraint analysis — return report

### Commits landed
- <SHA1> docs(research): pre-registration commit — Finviz-pool per-criterion binding-constraint analysis (D1)
- <SHA2> feat(research): Finviz-pool binding-constraint aggregator (D2)
- <SHA3> data(research): Finviz-pool binding-constraint analysis run (D3)
- <SHA4> docs(research): Finviz-pool binding-constraint findings (D4)
- <SHA5+> (if any) fix(research): adversarial review finding(s)

### Run details
- Qualifying evaluation_runs: <count> (date range <start>..<end>)
- Skipped runs (path missing): <count>; list: <runs>
- Total evaluations across qualifying runs: <count>
- Harness git SHA at run: <SHA>

### Results headline
- Bucket distribution: aplus=<n> watch=<n> skip=<n> error=<n> excluded=<n>
- Watch:A+ ratio: <ratio> overall (<n>/<n>)
- Top 3 production-gated blockers: <criterion: count, %>; <criterion: count, %>; <criterion: count, %>
- Near-A+ defensible count: <count> (<%> of watch bucket)
- Near-A+ doctrine-incompatible count: <count> (<%> of watch bucket)

### Tests
- Before: <baseline> passing
- After: <N> passing, 0 failing. New tests: <count>.

### Adversarial review verdict
- <NO_NEW_CRITICAL_MAJOR | findings summary>

### Deviations from brief
- <Empty if none. List judgment calls and rationale.>

### Open questions for orchestrator
- <Empty if none.>
```

---

## 11. If you get stuck

- **If `recompute_binding_prod_gated.py` doesn't expose a clean import surface** for the production-gated blocker computation: extract its logic into a small helper that both it and your aggregator call; flag as a research-branch refactor in the return report. Do NOT duplicate the logic.
- **If many evaluation_runs have `finviz_csv_path = NULL`** (legacy or non-Finviz-driven runs): document in the manifest; exclude from analysis (not in scope); proceed with the rest.
- **If the `data/finviz-inbox/rejected/` directory contains files referenced by past runs**: include them as qualifying (they were ingested at one point even if rejected later). Document the inclusion logic in the manifest.
- **If pre-registration is broken** (D3 ran before D1 committed): document explicitly; the operator can decide to discard and redo, or accept loss of pre-registration as a study limitation.
- **If the per-(ticker, run) detail output exceeds ~1MB**: add to gitignore; commit only the aggregated CSVs. Flag in return report.
