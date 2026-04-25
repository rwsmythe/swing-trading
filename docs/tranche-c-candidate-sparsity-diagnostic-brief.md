# Tranche C — Candidate-Sparsity Diagnostic Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Diagnose why the production A+ rate (~0.5% per ticker-day on the operator's Finviz-filtered universe) is ~120× higher than the Session 2c replay rate (0.0042% on SPX+NDX). Output is a diagnostic report identifying which criteria are binding, the universe-shape effect, and capital-sensitivity. **Diagnose, don't decide** — no production code changes, no proposed methodology revisions. Decision about whether to broaden criteria belongs to the operator after seeing findings.
**Expected duration:** 4–6 hours.
**Prepared:** 2026-04-24 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions, yfinance gotchas (especially `threads=False` ONLY on `yf.download()`; `Ticker.history()` does NOT accept `threads=`), MultiIndex squeeze pattern, TDD discipline, conventional-commits + no-amend rules.
2. `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` — V2.1 §V.F research evidence standard (named baseline, hypothesis, parameter choices, sensitivity, decision); §III principle 7 (time-budget anchor); §IV.C (provenance).
3. `reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md` — anti-patterns list, especially "infrastructure displacement" and "registry maximalism."
4. `research/studies/earnings-proximity-exclusion-results.md` — Session 2c evidence summary (commits `48320c8`, `3767639`). The 11-signal sparsity that triggered this diagnostic is documented there. Read the §"Open Issues" section.
5. `research/notes/historical-candidate-source-decision.md` — Session 2a's universe-choice memo. Documents the SPX+NDX selection and the fixed-universe concession.
6. `research/harness/earnings_proximity/` — the harness from Sessions 2b/2c. Critical: read `replay.py` for the eval driver and `fetchers.py` for cache helpers (post-housekeeping fixes inherited).
7. `research/harness/earnings_proximity/scripts/session2c_*.py` — reference scripts from housekeeping commit. Useful as starting point for diagnostic-run drivers; do NOT modify them.
8. `swing/evaluation/` — A+ criteria source code. The diagnostic instruments these to log per-criterion rejection rates. **Read-only consumption** per Phase isolation.
9. `swing/evaluation/criteria/` — individual criterion files (trend-template, VCP, RS, ADR, tightness, pullback, risk-feasibility, etc.). The diagnostic logs which of these is the binding constraint.
10. `swing/recommendations/sizing.py` — sizing math; potentially relevant if `risk_feasibility` is the binding constraint and capital scaling matters.
11. The current operator capital — read from `swing.config.toml` or wherever the production system reads it. The diagnostic uses this as the `1×` baseline.

**Skill posture.**
- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans`. The diagnostic question is settled; this session executes against it.
- Invoke `superpowers:test-driven-development` for any harness instrumentation that constitutes new code.
- Invoke `superpowers:verification-before-completion` before declaring done.
- After all code commits land + diagnostic report drafted, invoke `copowers:adversarial-critic`. **The review target this session is the diagnostic report's statistical conclusions, not the harness instrumentation code.** See §6 for review-prompting guidance specific to diagnostic conclusions.

---

## 1. Strategic context (compressed)

Session 2c (commits `0e04079..3767639`) ran the earnings-proximity-exclusion study with `defer` outcome. The decision was correct under the pre-registered protocol, but the underlying cause was extreme signal sparsity — 11 A+ signals across 504 trading days × 516 SPX+NDX tickers (0.0042% per ticker-day). Compared to production's observed ~0.5% per ticker-day on the Finviz-filtered ~80-ticker universe, that's a **120× per-ticker-day rate divergence**.

The operator (developer) flagged this as a systemic concern: "the tool is not finding enough candidates. It could be too restrictive because the capital is too low, or some other problem." The orchestrator scoped this diagnostic study to investigate.

**Hypothesis space (the search the diagnostic explores):**

1. **A+ criteria too restrictive in absolute terms.** The conjunction over-restricts even though each criterion is individually reasonable.
2. **A+ criteria too restrictive given the universe.** SPX+NDX is mature large-caps; Minervini-style setups should fire more often on small/mid-caps.
3. **Capital/sizing constraints filter pattern-valid candidates.** Operator hypothesis. If `risk_feasibility` or sizing math rejects setups, low capital makes this binding.
4. **Time-period regime bias.** 2024-04-19 → 2026-04-23 may be unusually inhospitable.
5. **Production vs replay behavioral divergence.** The harness reuses production `evaluate_one` but surrounding context (BatchContext, RS computation) is reimplemented; potential silent drift.
6. **Universe-source vs criteria-source mismatch.** Finviz user-filter pre-screens for A+-prone characteristics; SPX+NDX universe doesn't.

This session covers hypotheses 1, 2, 3, and partially 5 (parity-check via existing fixture). Hypotheses 4 and 6 are out of scope (different time periods + Finviz-universe reconstruction = separate studies).

**Output: a diagnostic report. No production code changes. No methodology revisions. Decision on what (if anything) to do with the findings is operator's call.**

---

## 2. Scope — 5 deliverables (no early-return valve)

| # | Deliverable | Kind |
|---|-------------|------|
| D0 | Housekeeping — track this brief (and any other untracked drift) | Docs |
| D1 | Universe-variant infrastructure: load Russell 3000 (or fallback S&P 1500); make universe selection configurable in harness or driver | Code (instrumentation) |
| D2 | Per-criterion rejection logging: instrument the evaluation path to log which criterion fails for each (ticker, date) pair | Code (instrumentation) |
| D3 | Capital-scaling parameter: make capital configurable in the diagnostic driver; `--capital-multiplier` flag | Code (driver) |
| D4 | Run the diagnostic — 2 universes × 2 capital multipliers × the same 2-year window = 4 runs. Cache outputs alongside Session 2c artifacts | Run + raw outputs |
| D5 | Diagnostic report: `research/studies/candidate-sparsity-diagnostic.md` with per-criterion binding-constraint analysis, universe-shape effect quantification, capital-sensitivity findings, no production-code recommendations | Docs |
| D6 | Adversarial review on D5 (the diagnostic report) | Review |

### Explicitly out of scope

- **Any change to `swing/*` production code.** Read-only consumption only. The harness is allowed to import production criteria and call them, but cannot mutate any production module.
- **Any methodology revision recommendation in D5.** The diagnostic report identifies findings; it does NOT propose criteria changes, sizing changes, or universe broadening. Those are operator decisions made after reading the report.
- **Time-period sensitivity (hypothesis 4).** Same 2-year window as Session 2c. Adding multiple time periods balloons scope.
- **Finviz-universe reconstruction (hypothesis 6).** Historical Finviz CSVs don't exist; reconstructing them is a multi-week data project.
- **Any production-vs-replay behavioral parity test beyond what existing harness fixtures cover.** Hypothesis 5 is partially addressed via existing harness tests (which cover `evaluate_one` reuse correctness); deeper parity work would require side-by-side runs against the production DB which expands scope.
- **Any new study question or follow-on diagnostic.** This session produces ONE diagnostic report. Follow-ups are operator's call.

---

## 3. Binding conventions

- **Branch:** `main`.
- **Commits:** conventional-commits. No Claude co-author footer. No `--no-verify`. No amending.
- **TDD:** apply to D1, D2, D3 (instrumentation that constitutes new code). D4 is a run; D5 is documentation.
- **Tests:** fast suite green after every commit. Baseline going in: 634 + housekeeping additions.
- **Ruff:** no new violations beyond baseline 81; narrow `# noqa` with reasons if needed.
- **Phase isolation:** `swing/*` is consumed READ-ONLY. No mutations. No new files under `swing/`. No DB writes to `swing.db`. Diagnostic outputs go to `research/` and `~/swing-data/research-cache/` (or a sibling diagnostic-cache directory).

---

## 4. Task specifications

### D0 — Housekeeping

```bash
git status
```

Stage untracked files relevant to this session (likely just this brief):

```bash
git add docs/tranche-c-candidate-sparsity-diagnostic-brief.md
# add any other untracked-but-session-relevant files
```

Commit message:

```
docs: track Tranche C candidate-sparsity diagnostic brief
```

### D1 — Universe-variant infrastructure

**Primary universe target: Russell 3000.**

**Sourcing options (try in order):**
1. **iShares IWV ETF holdings.** Downloadable from `https://www.ishares.com/us/products/239714/ishares-russell-3000-etf` (CSV link on the holdings tab). Most authoritative source.
2. **Vanguard VTHR ETF holdings.** Similar pattern.
3. **A static Wikipedia or other published list.** Less authoritative but reproducible.
4. **Fallback: S&P 1500.** S&P 500 + S&P 400 (mid) + S&P 600 (small). Multiple ETF holdings sources (IVV + IJH + IJR). Smaller universe (~1500 vs ~3000) but easier to source.

Implementer's call on data source if Russell 3000 sourcing has friction. Document choice + URL + fetch date in the diagnostic report.

**Files to create or modify:**
- `research/harness/earnings_proximity/universe_variants.py` (new) — function `load_universe_variant(name: Literal['spx_ndx', 'russell_3000', 'sp_1500'])` returning a list of tickers. SPX+NDX uses the existing `swing.evaluation.rs.load_universe` (read-only). Russell 3000 / S&P 1500 fetched from chosen source, cached locally as a CSV.
- `research/harness/earnings_proximity/scripts/diagnostic_*.py` (new) — diagnostic-run drivers (analogous to `session2c_*.py` but parameterized by universe + capital-multiplier).

**Cache for universe lists:** `~/swing-data/research-cache/universe-snapshots/` (sibling to existing OHLCV/earnings caches). Store as `russell_3000_2026-04-24.csv` (date-stamped). Re-fetch if stale > 30 days.

**Tests:**
- `load_universe_variant('spx_ndx')` returns the same tickers as `swing.evaluation.rs.load_universe` (the canonical SPX+NDX universe).
- `load_universe_variant('russell_3000')` returns ≥2500 tickers (sanity check; Russell 3000 typically has 3000-3050 active holdings).
- Cache hit/miss behavior tested.
- Stale-cache refetch behavior tested.

**Commit message:**

```
feat(research): universe-variant loader for diagnostic study

Adds load_universe_variant() supporting SPX+NDX (existing), Russell 3000
(primary diagnostic target), and S&P 1500 (fallback). Universe lists
cached at ~/swing-data/research-cache/universe-snapshots/ with date-stamped
filenames; re-fetch if stale > 30 days.
```

### D2 — Per-criterion rejection logging

**Goal:** for each (ticker, date) pair the harness evaluates, log which criterion (if any) caused it to fail bucket assignment to A+. Aggregated over the run, this produces the "which criterion is the binding constraint?" answer.

**Approach:**

The production `evaluate_one` returns a `CandidateContext` with `bucket` ∈ {`'aplus'`, `'watch'`, `'skip'`, `'excluded'`}. A ticker that fails A+ but passes lower buckets has been rejected by some specific criterion. Read the criterion-evaluation logic in `swing.evaluation.criteria/` to identify the per-criterion pass/fail — the existing logic likely already produces a per-criterion result list (check; if not, the diagnostic instrumentation may need to call individual criteria directly).

**File to create:**
- `research/harness/earnings_proximity/instrumented_replay.py` (new) — wraps `replay.replay()` with per-(ticker, date) per-criterion result logging. Yields a stream of records like:
  ```python
  {
      'ticker': str,
      'date': date,
      'bucket': str,  # final bucket
      'criterion_results': dict[str, bool],  # {'trend_template': True, 'vcp': False, ...}
      'binding_constraint': str | None,  # name of first failing criterion, None if A+
  }
  ```

**Output:** the instrumented replay writes per-(ticker, date) records to a CSV alongside the standard metrics output. Aggregated counts (per criterion: how many ticker-date pairs did this criterion reject?) computed in D5 analysis.

**Tests:**
- Instrumented replay produces records for every ticker-date pair the underlying replay evaluates.
- For known fixtures (a ticker with known A+/watch/skip outcomes), the per-criterion result dict matches expected values.
- Aggregation logic correctly sums per-criterion rejection counts.

**Commit message:**

```
feat(research): per-criterion rejection logging in instrumented replay

Wraps replay.replay() to log per-(ticker, date) per-criterion pass/fail
results, enabling identification of binding constraints in candidate-sparsity
diagnostic. Writes per-pair records to CSV alongside standard metrics
output. No mutation of production swing.evaluation modules.
```

### D3 — Capital-scaling parameter

**Goal:** vary the capital level the harness uses for sizing-feasibility checks, to test whether `risk_feasibility` or related sizing criteria are binding.

**Files:**
- `research/harness/earnings_proximity/scripts/diagnostic_run.py` (new) — driver that takes a `--capital-multiplier` CLI flag. Reads operator's current production capital from wherever the production system reads it (likely `swing.config.toml` `[capital]` section or DB query — confirm against current production behavior). Multiplies by the flag value (`1.0`, `5.0`) to construct the harness's effective capital for the run.
- The harness's sizing path (probably via `swing.recommendations.sizing.compute_shares`) needs to be parameterized by capital. If it currently reads capital from a fixed source, the diagnostic driver needs to inject the multiplied value.

**Acceptance:**
- `diagnostic_run.py --capital-multiplier 1.0` produces results consistent with what Session 2c produced (modulo D2 instrumentation overhead — same A+ count expected).
- `diagnostic_run.py --capital-multiplier 5.0` accepts more candidates if `risk_feasibility` was binding at 1×; produces same count if it wasn't.
- Capital multiplier is recorded in run-manifest provenance.

**Commit message:**

```
feat(research): capital-multiplier flag on diagnostic driver

Allows the diagnostic to test whether risk_feasibility or related sizing
criteria are binding constraints on A+ rate by running the same evaluation
with multiplied capital (1×, 5×). Recorded in run manifest.
```

### D4 — Run the diagnostic

**4 runs total:**

| Run | Universe | Capital multiplier |
|---|---|---|
| A | SPX+NDX (baseline; matches Session 2c) | 1.0 |
| B | SPX+NDX | 5.0 |
| C | Russell 3000 (or S&P 1500 fallback) | 1.0 |
| D | Russell 3000 (or S&P 1500 fallback) | 5.0 |

**Same 2-year window as Session 2c** (2024-04-19 → 2026-04-23). Same earnings calendar source (yfinance). Same harness with C3+C4 housekeeping fixes inherited.

**Output for each run:**
- Standard metrics CSV (signal counts, expectancy, etc. — though for the diagnostic, signal counts and per-criterion rejection breakdowns matter more than expectancy).
- D2 per-(ticker, date) per-criterion CSV.
- Run manifest with provenance.

**Cache pre-warming:**
- SPX+NDX OHLCV is already cached from Session 2c.
- Russell 3000 OHLCV needs cache warm-up. Estimate: ~3000 tickers × 504 trading days = a few hours of cold yfinance fetch. Plan for ~60-90 min wall-clock for first run; subsequent runs hit cache.
- Russell 3000 earnings: similar cold-fetch overhead.

**If cache warm-up exceeds session budget:** ship D0-D3 + warm cache + a partial run (e.g., SPX+NDX 1× and 5× only) as a 2c-a-style commit set; defer Russell 3000 runs to a thin follow-up. Pre-authorized.

**Commit:**

```
data(research): diagnostic study run results — 4 runs (universe × capital matrix)

Universe variants: SPX+NDX (Session 2c baseline) + Russell 3000 (broader
small-mid-cap universe). Capital multipliers: 1× (operator's current capital)
and 5× (sizing-feasibility sensitivity). 2-year window matching Session 2c
(2024-04-19 → 2026-04-23).
```

### D5 — Diagnostic report

**File to create:** `research/studies/candidate-sparsity-diagnostic.md`

**Status:** designed end-to-end as a "diagnose, don't decide" output. **No production-code recommendations.** Findings inform operator decisions; this report does not make them.

**Required sections:**

```markdown
# Candidate-Sparsity Diagnostic

**Date:** 2026-04-24
**Companion to:** Session 2c evidence summary (`./earnings-proximity-exclusion-results.md`)
**Status:** Diagnostic — no production-code recommendations.
**Question motivating the diagnostic:** Why is the production A+ rate (~0.5% per ticker-day, Session 2a observation) ~120× higher than the Session 2c replay rate (0.0042% on SPX+NDX)?

## Hypotheses tested

[List the 3 hypotheses from §1 of this brief that this diagnostic actually tests, with citation to the original framing.]

## Methodology

[Universe variants, capital multipliers, 2-year window matching Session 2c. Cite the harness, the housekeeping commits inherited, the run manifests.]

## Results

### A+ rate by universe × capital

[4-cell matrix: SPX+NDX × {1×, 5×} and Russell 3000 × {1×, 5×}. Per-cell signal count + per-ticker-day rate.]

### Per-criterion binding-constraint analysis

[For each criterion (trend_template, VCP, RS, ADR, tightness, pullback, risk_feasibility, etc.): how many ticker-date pairs did this criterion reject? Across the 4 runs, which criteria are most often binding?]

### Universe-shape effect

[Compare SPX+NDX vs Russell 3000 A+ rate at constant capital. What's the magnitude of the difference? Which criteria are responsible?]

### Capital-sensitivity finding

[Compare 1× vs 5× capital at constant universe. Does A+ rate change? If so, which criteria's pass rate changed?]

## Findings (descriptive, not prescriptive)

[Bullet list of empirical findings. Examples of phrasing:
- "Criterion X is the binding constraint in N% of ticker-date pairs across all four runs."
- "Universe variant Russell 3000 produces M× the A+ rate of SPX+NDX at constant capital, attributable primarily to criteria Y and Z."
- "Capital scaling 1× → 5× changes A+ rate by P% on SPX+NDX, attributable to risk_feasibility relaxation."]

## What this diagnostic does NOT say

[Explicit list of non-conclusions. Examples:
- "This diagnostic does NOT recommend changing any A+ criterion threshold."
- "This diagnostic does NOT recommend broadening the production universe."
- "This diagnostic does NOT make any claim about the edge quality of A+ candidates — only about their rate."
- "This diagnostic uses the same fixed-universe and survivorship-biased data as Session 2c; findings inherit the same survivorship caveats."]

## Caveats and limitations

[Explicit:
- Survivorship bias same as Session 2c.
- Fixed-universe at run date; no point-in-time membership reconstruction.
- Russell 3000 is a current snapshot, not historical.
- 2-year window is a single regime; broader-time-period analysis is future work.
- Production-vs-replay parity is partial; only existing harness fixture coverage.]

## Open questions for the operator

[Questions the operator might want to answer based on findings, but that this diagnostic does not answer:
- "Should criterion X's threshold be relaxed?"
- "Should the production universe be broadened?"
- "Is the operator's current capital level a binding constraint on workflow?"]
```

**Acceptance:**
- All 4 runs' results reported.
- Per-criterion binding-constraint analysis shows pass rates per criterion across the 4 runs.
- Findings are descriptive (numbers + interpretation) not prescriptive (no "should" statements about production code).
- Caveats section disclosure aligns with Session 2c precedent.

**Commit message:**

```
docs(research): candidate-sparsity diagnostic report

Diagnostic study identifying binding constraints on A+ rate across 4 runs
(SPX+NDX + Russell 3000) × (1×, 5× operator capital). Findings are
descriptive only; no production-code recommendations. Decision on what to
do with findings is operator's call.
```

---

## 5. Adversarial review (after D5 lands)

**The review target this session is the diagnostic report's statistical conclusions, not the harness instrumentation code.** Similar to Session 2c's adversarial-review framing (which was on evidence-summary content, not on code).

Use a prompt approximating this shape when invoking `copowers:adversarial-critic`:

> "Review this diagnostic report on candidate-sparsity in a swing-trading harness. The report identifies which evaluation criteria are binding constraints on A+ candidate rate across two universe variants and two capital levels. Focus your review on:
>
> 1. Whether per-criterion rejection counts are correctly attributed (no double-counting; the binding-constraint identification logic is sound).
> 2. Whether universe-shape effects vs criteria-effects are properly separated in the analysis.
> 3. Whether capital-sensitivity findings are interpreted correctly (is 5× capital actually changing what gets accepted, or is some other factor binding even at 5×?).
> 4. Whether the report stays disciplined as 'diagnose, don't decide' — i.e., does it sneak in implicit production-code recommendations through 'should' framings, threshold suggestions, or rhetorical loading?
> 5. Whether the caveats section adequately discloses survivorship bias, fixed-universe, regime-specificity (single 2-year window), and Russell-3000-current-snapshot limitations.
> 6. Whether per-criterion analysis matches the production criteria as actually implemented (the diagnostic could mis-attribute a rejection if it hits criteria in different order than production).
> 7. Whether numerical results have appropriate uncertainty annotations or sample-size context.
> 8. Whether 'open questions for operator' section is genuinely open-ended or is a list of leading questions that imply specific actions."

Iterate to `NO_NEW_CRITICAL_MAJOR`. ACCEPTED-with-rationale findings stay accepted (e.g., the survivorship-bias caveat is already present and inherited from Session 2c; if reviewer asks for more, that's accepted as inherited disclosure).

**Watch items the reviewer is likely to probe:**
- Implicit recommendations dressed as findings ("only 5% of ticker-date pairs pass criterion X" with rhetorical implication "this seems too restrictive").
- Universe-comparison artifacts where SPX+NDX and Russell 3000 differ on dimensions other than universe (e.g., if Russell 3000 has different RS-rank distribution by construction, comparing A+ rates without normalizing for that is an artifact).
- Unfalsifiable conclusions ("the rule appears too restrictive" without a specification of what "less restrictive" would look like or how to test it).
- Capital-sensitivity confounds (if 5× capital also changes which positions can be sized, sample composition changes — comparison is across different populations).

Fix findings in a new commit per no-amend.

---

## 6. Done criteria

- D0–D5 shipped (D6 review fixes if needed).
- Fast suite green.
- No new ruff violations.
- 4 runs completed, results in `research/studies/candidate-sparsity-diagnostic.md`.
- Adversarial review verdict: `NO_NEW_CRITICAL_MAJOR`.
- Diagnostic report stays "diagnose don't decide" — no production-code recommendations.
- Return report produced.

---

## 7. Return report format

```
## Tranche C candidate-sparsity diagnostic return report

### Commits landed
- <SHA> docs: track Tranche C candidate-sparsity diagnostic brief                          (D0)
- <SHA> feat(research): universe-variant loader for diagnostic study                        (D1)
- <SHA> feat(research): per-criterion rejection logging in instrumented replay              (D2)
- <SHA> feat(research): capital-multiplier flag on diagnostic driver                        (D3)
- <SHA> data(research): diagnostic study run results — 4 runs (universe × capital matrix)   (D4)
- <SHA> docs(research): candidate-sparsity diagnostic report                                (D5)
- <SHA> fix(research): address Tranche C diagnostic adversarial-review findings             (D6 — if needed)

### Tests
- Before: <N> passing (post-housekeeping baseline).
- After: <N> passing, 0 failing. New tests: <M>.

### 4-run matrix — A+ rate per ticker-day
| Universe | Capital × | Signal count | Per-ticker-day rate |
|---|---|---|---|
| SPX+NDX (Session 2c baseline) | 1× | <N> | <%> |
| SPX+NDX | 5× | <N> | <%> |
| Russell 3000 (or S&P 1500 if fallback used) | 1× | <N> | <%> |
| Russell 3000 (or S&P 1500 if fallback used) | 5× | <N> | <%> |

### Top-3 binding criteria (across runs)
[List which criteria most often blocked A+ assignment.]

### Universe data source used
<iShares IWV / Vanguard VTHR / Wikipedia / S&P 1500 fallback>. URL: <...>. Fetch date: <YYYY-MM-DD>.

### Cache state after session
- OHLCV (post-session): <N> tickers, <MB>.
- Earnings: <N> tickers, <MB>.
- Universe snapshots: <list of files>.

### Adversarial review — summary
- Rounds: <N>
- Base SHA: <D5 SHA>
- Thread ID: <Codex MCP>
- Findings: <N> critical / <N> major / <N> minor
- FIXED: <short summary>
- ACCEPTED-with-rationale: <short summary>
- Verdict: NO_NEW_CRITICAL_MAJOR at Round <N>

### "Diagnose, don't decide" compliance
- [x] No production-code recommendations.
- [x] Findings are descriptive, not prescriptive.
- [x] "What this diagnostic does NOT say" section present and substantive.
- [x] Caveats section discloses all known biases.

### Deviations from brief
<empty if none>

### Items flagged but not done (scope discipline)
<bullets>

### Open questions for orchestrator
<bullets>
```

---

## 8. If you get stuck

- If Russell 3000 sourcing has friction (paywall, scrape blocking, API failure), fall back to S&P 1500. Document the choice and rationale in the report. Do NOT spend more than ~30 min on data sourcing — the diagnostic value is in the cross-universe comparison, not in choosing the most authoritative broad universe.
- If the production criteria don't expose per-criterion pass/fail in a way that's easy to instrument, a workaround is to call individual criteria directly from `swing.evaluation.criteria.*` modules — these are pure functions per the LOC inventory in Session 2a's decision memo. Do NOT modify the production `evaluate_one` to expose more state.
- If the cache warm-up for Russell 3000 exceeds expected time and you're approaching session-budget limits, ship the SPX+NDX runs (A and B) plus warm cache for Russell, defer the Russell runs (C and D) to a thin follow-up. Better to have 2 of 4 runs reported with discipline than 4 of 4 reported in a rushed session.
- If a test you write passes under both pre-change and post-change harness behavior, rewrite it (`memory/feedback_regression_test_arithmetic.md`).
- If the diagnostic's findings are surprising in ways that suggest a bug in the harness or in the production criteria, **do NOT chase the surprise mid-session**. Document the observation in the report's "Open questions" section and let the operator triage.
- If you find yourself wanting to suggest production-code changes ("we should relax criterion X"), STOP. The diagnostic is "diagnose don't decide." Production-code suggestions in this report violate scope. Findings + open questions for operator only.
