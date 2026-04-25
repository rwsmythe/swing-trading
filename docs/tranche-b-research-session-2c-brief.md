# Tranche B-research session 2c — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Run the full earnings-proximity-exclusion parameter sweep against the populated harness from Session 2b, pre-register decision-tier thresholds BEFORE viewing results, write the evidence summary with observed values + tier mapping + final decision, and run adversarial review on the statistical conclusions (not on code). Ship one of: `reject` / `shadow` / `promote` / `defer`.
**Expected duration:** 5–8 hours. Split contingency pre-authorized (see §1).
**Prepared:** 2026-04-24 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions, gotchas (especially yfinance rate-limit handling for the full-universe cache warm-up), TDD discipline, conventional commits / no-amend / no-Claude-co-author rules.
2. `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` — governing strategy. Focus on §V.F (research evidence standard: named baseline, explicit hypothesis, parameter choices recorded, sensitivity check, clear result summary, decision), §VII.B (toleranced parity), §IV.C (provenance), §III principle 7 (time-budget anchor).
3. `reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md` — binding clarifications. Anti-patterns list — pre-registration violations and post-hoc rationalization are exactly the failure modes this session is designed to prevent.
4. `research/method-records/earnings-proximity-exclusion.md` — method record. Note `blackout_trading_days` parameter, variants {3, 5, 7, 10}, absent-data → "do NOT exclude, flag for review" rule.
5. **CRITICAL: `research/studies/earnings-proximity-exclusion.md` — study design with the survivorship-bias interpretation protocol.** Read this end-to-end. The protocol's "Decision tiers" subsection and the "What Session 2c MUST include / MUST NOT do" subsections are binding for this session's evidence-summary work.
6. `research/notes/earnings-calendar-sources.md` — Session 2a calendar evaluation. Decision: yfinance `Ticker.get_earnings_dates()`. Reliability caveats apply.
7. `research/notes/historical-candidate-source-decision.md` — Session 2a data decision. Option B synthetic replay; fixed-universe concession; binding implications for the harness.
8. `research/harness/earnings_proximity/README.md` and source — Session 2b's harness. Read `run.py` for the CLI interface; `replay.py`, `simulator.py`, `variants.py`, `metrics.py` for behavioral semantics; `provenance.py` for manifest fields.
9. `docs/tranche-b-research-session-2b-brief.md` and Session 2b's return-report context — particularly the cache state and the "smoke evidence" section. Note that 2b's adversarial review caught and fixed the universe-contract bug (Round 1 Major #1) and the dropped-signal-count multiplier (Round 1 Major #3); your full run inherits the post-fix harness.
10. Recent commits on `main` for context on the RS-universe refresh that landed before this session.

**Skill posture.**

- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans`. The methodology is locked by the study design + survivorship-bias protocol.
- Invoke `superpowers:test-driven-development` only for any harness-tuning code commits (the `_FORWARD_BUFFER_BARS` change, etc.). Most of this session is execution + analysis, not new code.
- Invoke `superpowers:verification-before-completion` before declaring done.
- **Mandatory:** invoke `copowers:adversarial-critic` for review of the evidence-summary content. **The review target this session is statistical conclusions, not code** — see §5 for review-prompting guidance specific to this target.

---

## 1. Session shape — pre-registration discipline + split contingency

This session has a hard commit-order discipline: **pre-registration BEFORE result viewing.** Specifically:

- **D1 (pre-registration commit)** must land BEFORE D3 (study run). The implementer drafts decision-tier thresholds — effect-size minimums, statistical-significance criteria, sensitivity-check requirements — based on the survivorship-bias protocol in the study design AND on a sample-size estimate derived from the cache's universe and window. Observed values are stubbed as `<TBD>` placeholders. The commit is concrete and reviewable.
- **D2 (cache warm-up)** can land before, after, or interleaved with D1 — it's idempotent and view-only of cache hit/miss, not of metrics.
- **D3 (run study)** must land AFTER D1. Once D3 ships, the implementer has seen the observed values; thresholds set after that point are not pre-registered.
- **D4 (evidence summary)** fills in the observed values, applies the pre-registered thresholds to assign a tier, and lands the decision (reject / shadow / promote / defer).

If you find yourself wanting to revise the pre-registered thresholds AFTER seeing D3's output, **stop**. The protocol's whole point is to prevent that. Document the desire to revise in the evidence summary's "Open issues" section as a known limitation, but do not actually revise.

### Split contingency — pre-authorized

If the full-universe cache warm-up (D2) plus full-study run (D3) push wall-clock past 6 hours combined, **split the session after D3 into 2c-a (D0–D3) and 2c-b (D4–D6)**:

- **2c-a commits:** D0 (housekeeping) + D1 (pre-registration) + D2 (cache warm-up) + D3 (study run + raw outputs committed). Pre-registration discipline preserved across the split because D1 commits before D3 within 2c-a.
- **2c-b session:** opens with raw output already committed; the implementer composes the evidence summary (D4) and runs adversarial review (D5/D6).
- **Commit semantics:** each commit must be clean and green. Observed numerical outputs in `metrics.csv` and `run_manifest.json` are committed in 2c-a; the evidence summary's prose interpretation is in 2c-b.

Signals that trigger the split:
- Full-universe cache warm-up exceeds 90 minutes wall-clock.
- yfinance throttling sustained at >60 sec per ticker batch.
- Implementer judgment that D4's analysis quality would suffer from session fatigue.

Less aggressive split — if D2+D3 fit but D4 looks tight: ship D4 in this session, run adversarial review (D5) in a thin follow-up. Implementer judgment.

### Explicitly out of scope

- Any modification to the harness's behavioral logic (replay driver, simulator, variants, metrics). Cosmetic / quota-saving tweaks like `_FORWARD_BUFFER_BARS = time_cap_days * 3` are allowed if they don't change semantics; flag in return report.
- Any modification to the method record `research/method-records/earnings-proximity-exclusion.md` or the study design `research/studies/earnings-proximity-exclusion.md`. The decision tiers + survivorship-bias protocol are locked. If the analysis surfaces a methodology concern that requires study-design amendment, document in the evidence summary's "Open issues" and flag for orchestrator — do NOT amend mid-session.
- Any modification to `swing/*`. The harness reads `swing/` modules read-only; this session keeps that invariant.
- Any second study, sensitivity analysis beyond what is pre-registered, or follow-on research. The decision (reject/shadow/promote/defer) closes V2.1 §X tranche 2's "complete one decision-grade study" goal; further work is later phases.
- Any manual delistings list, paid-data evaluation, or alternative-vendor cross-check. Bootstrap-first per V2.1 §V.E. If results are decision-boundary-sensitive, the decision tier is `defer`, not "let's get better data and try again right now."
- Any change to `reference/rs-universe.csv`. The user refreshed it before this session per Option A from the orchestrator decision; this session uses it as-is.

---

## 2. Session deliverables

| # | Deliverable | Kind |
|---|-------------|------|
| D0 | Housekeeping — track any leftover untracked drift | Docs |
| D1 | Pre-registration document at `research/studies/earnings-proximity-exclusion-results.md` with thresholds + observed-values stubbed `<TBD>` | Docs |
| D2 | Full-universe OHLCV + earnings cache warm-up (~500–600 tickers × 2-year window) | Cache (out-of-repo) + commit of any harness tweaks if needed |
| D3 | Full study run: 5 variants × full universe × full window. Commits raw `metrics.csv` and `run_manifest.json` from the run | Data outputs (committed) |
| D4 | Evidence summary writeup at `research/studies/earnings-proximity-exclusion-results.md`: replace `<TBD>` with observed values + tier mapping + decision | Docs |
| D5 | Adversarial review on the evidence summary content | Review |
| D6 | (if needed) Fix commit absorbing review findings | Docs |

---

## 3. Task specifications

### D0 — Housekeeping

Standard pre-session check.

```bash
git status
```

Stage any untracked files relevant to recent sessions (likely just this brief, plus the RS-universe refresh artifacts if those weren't already committed by the user):

```bash
git add docs/tranche-b-research-session-2c-brief.md
# add any other untracked-but-session-relevant files surfaced by git status
git commit -m "docs: track session-2c dispatch brief"
```

If the working tree is clean, skip this commit and start with D1.

### D1 — Pre-registration commit

**This commit MUST land before D3.** Create `research/studies/earnings-proximity-exclusion-results.md` with the structure below. Observed values are stubbed `<TBD>` and filled in D4.

#### Pre-registration content requirements

The pre-registration MUST include:

1. **Sample-size estimate.** Compute or estimate expected total signal count and per-variant signal count BEFORE looking at the actual D3 output. Use the cache's known universe size (~500–600 tickers post-refresh) × replay window (~504 trading days) × an A+ rate estimate from the smoke run or from the production `candidates` table audit (Session 2a found ~2 distinct A+ pairs across 5 days = ~0.4 A+ ticker-pairs/day in production; extrapolating to ~500 tickers × ~504 days needs care because production also runs against ~80 Finviz tickers/day, not 500). State your sample-size assumption explicitly so the reviewer can probe it.

2. **Effect-size thresholds per metric.** For EACH metric (expectancy, gap-through rate, gap-through magnitude, signal volume), specify:
   - **Strong-signal threshold** in absolute units (e.g., "expectancy delta ≥ 0.15R", "gap-through rate reduction ≥ 5 percentage points", "signal-volume reduction ≤ 30%").
   - **Moderate-signal threshold.**
   - **Weak/null band** (numerical range that maps to the `defer` tier).
   - **Negative threshold** (the rule materially harms expectancy or risk).

3. **Statistical-significance criteria.** Pre-register the inference framework you will use:
   - Confidence intervals for proportion (gap-through rate) — e.g., Wilson 95% CI.
   - Confidence intervals for mean R (expectancy) — bootstrap with N=10,000 resamples; or t-interval if you commit to it.
   - Multiple-comparison correction across 5 variants — explicitly Bonferroni, Holm-Bonferroni, or "no correction with rationale" (the latter requires a pre-registered argument that the comparisons aren't independent in the relevant sense).
   - Pre-commit to whether `p<0.05` (or equivalent CI threshold) is required for `promote`, or whether effect size alone — independent of significance — drives tier assignment.
   
   **Recommended posture:** Effect-size-driven thresholds with confidence intervals reported alongside, NOT pure p-value thresholds. Reasoning: with the expected sample size, anything that's significant at p<0.05 is also a sizable effect, but not all sizable effects will be significant. Document your choice either way.

4. **Sensitivity-check requirements.** Pre-register what you'll check ALONGSIDE the chosen X (if you promote):
   - Adjacent X values' effect sizes (e.g., if X=5 wins, also report X=3 and X=7's effects to confirm a smooth response surface).
   - Subset analysis (e.g., expectancy by year — does the rule work in 2024 and 2025, or only one?).
   - Robustness check on absent-data ticker count — if absent-data tickers are >10% of signals, flag.

5. **Survivorship-bias protocol checkboxes.** Pre-register that you will:
   - [ ] Report absolute metrics with "survivorship-biased lower bound" caveats.
   - [ ] Report relative metrics with "magnitude likely understated" notes.
   - [ ] Map observed-value-to-tier per the protocol's Decision Tiers subsection.
   - [ ] Disclose ALL three biases in the evidence summary: survivorship (delisted-ticker exclusion), fixed-universe (broader Finviz universe in production), universe-staleness (RS-universe-CSV-currency).

6. **Anti-rationalization guard.** State explicitly: "If observed results fall in the weak/null band per the pre-registered thresholds, the decision is `defer`, not `reject`. The survivorship-bias protocol's interpretation rule is binding."

#### Pre-registration document structure

```markdown
# Earnings-Proximity Exclusion — Evidence Summary

**Method record:** `../method-records/earnings-proximity-exclusion.md`
**Study design:** `./earnings-proximity-exclusion.md`
**Status:** PRE-REGISTERED (observed values pending Session 2c D3 run); will become FINAL after D4.
**Pre-registration commit:** `<this commit's SHA — fill in>`
**Decision:** <TBD — reject / shadow / promote / defer>

---

## Pre-registration

*This section is committed BEFORE the study runs (D1). Subsequent sections are filled in D4 after D3's output is observed. Pre-registration prevents post-hoc rationalization per the study design's survivorship-bias interpretation protocol.*

### Sample-size estimate

<assumption + arithmetic>

### Decision-tier thresholds per metric

| Metric | Strong (`promote`) | Moderate (`shadow`) | Weak/null band (`defer`) | Negative (`reject`) |
|---|---|---|---|---|
| Expectancy delta vs X=0 | <TBD pre-reg> | ... | ... | ... |
| Gap-through rate reduction (pp) | ... | ... | ... | ... |
| Gap-through magnitude reduction | ... | ... | ... | ... |
| Signal volume cost | ... | ... | ... | ... |

### Statistical-significance framework

<inference type per metric, multiple-comparison handling, pre-commit on whether significance is required for promote>

### Sensitivity-check requirements

<list>

### Survivorship-bias protocol — pre-registered checkboxes

(populated in D4 with [x] confirmations or explicit deviation notes)

### Anti-rationalization clause

<verbatim per brief §3 D1 item 6>

---

## Observed results

*Populated in D4 after D3 ships.*

<sections stubbed: variant-by-variant results, confidence intervals, sensitivity checks, etc.>

---

## Tier assignment

*Populated in D4.*

<observed-value-to-tier mapping per pre-registered thresholds>

---

## Decision

*Populated in D4.*

<reject / shadow / promote (with chosen X) / defer — with citation back to tier assignment>

---

## Discussion

*Populated in D4.*

<survivorship-bias caveats, data-quality footnotes, open issues>
```

**Acceptance for D1:**
- Document committed under `research/studies/earnings-proximity-exclusion-results.md`.
- All fields in §"Pre-registration" populated with concrete numbers / criteria / checkboxes (not `<TBD>` placeholders for the pre-reg fields themselves — those are for the OBSERVED-results sections only).
- Commit message clearly identifies the pre-registration role and references this brief.

**D1 commit message:**

```
docs(research): pre-register tier thresholds for earnings-proximity-exclusion analysis

Locks decision-tier mapping criteria BEFORE running the study, per the
survivorship-bias interpretation protocol in the study design. Observed
values, tier assignment, and final decision are populated in D4 after the
D3 study run commits raw outputs.

Pre-registered:
- Sample-size estimate based on cache state and universe.
- Effect-size thresholds for each of expectancy / gap-through rate /
  gap-through magnitude / signal-volume metrics across promote / shadow
  / defer / reject tiers.
- Statistical-inference framework (CIs vs p-values; multiple-comparison
  handling).
- Sensitivity-check requirements for promoted X.
- Anti-rationalization clause: weak/null observed → defer, never reject.

Per brief §3 D1; per study design's Survivorship-bias interpretation
protocol; per V2.1 §V.F research evidence standard.
```

### D2 — Full-universe cache warm-up

The harness's `fetchers.py` is idempotent and per-ticker. Identify the universe ticker list (from `reference/rs-universe.csv` post-refresh) plus benchmark (`SPY`). Run cache warm-up for the full universe over the 2-year window.

Suggested approach:

```python
# Quick script you may write inline, or a CLI flag if the harness already supports it.
from research.harness.earnings_proximity.fetchers import load_ohlcv, load_earnings
from swing.evaluation.rs import load_universe
from datetime import date, timedelta
from pathlib import Path

universe = load_universe(Path("reference/rs-universe.csv"))
tickers = list(universe.tickers) + ["SPY"]  # confirm actual attribute
end = date.today()
start = end - timedelta(days=730)  # ~2 years
cache_dir = Path.home() / "swing-data" / "research-cache"

ohlcv = load_ohlcv(tickers, start, end, cache_dir / "ohlcv")
earnings = load_earnings(tickers, cache_dir / "earnings")
```

Use `load_*_with_stats` if you want telemetry. `yf.download()` with `threads=False` per CLAUDE.md. Per-ticker `Ticker.get_earnings_dates(limit=30)` for earnings.

**Acceptance:**
- Cache populated for the full universe + benchmark.
- Cache stats logged: hits/misses by class.
- No yfinance API misuse (CLAUDE.md gotchas: `threads=False` on `yf.download` ONLY; MultiIndex squeeze; timezone in ET).

**D2 commit (if any code changes):** depends. If you write a one-off script `research/harness/earnings_proximity/warm_cache.py`, commit it. If you tighten `_FORWARD_BUFFER_BARS = time_cap_days * 3` per Session 2b's flag, commit that. If you make no code changes — the warm-up just populates an out-of-repo cache — there's nothing to commit; D2 is a state change, not a code change. Skip the commit and proceed to D3.

If you DO commit, message:

```
feat(research): full-universe cache warm-up support / harness tuning for full study

<describe specific change>
```

### D3 — Full study run

Invoke the harness's CLI in full-window mode:

```bash
python -m research.harness.earnings_proximity.run \
    --window-years 2 \
    --variants 0,3,5,7,10 \
    --output-dir research/harness/earnings_proximity/full-run-out/
```

(Adjust flag names to whatever the harness's `run.py` actually accepts. Read the source to confirm.)

Verify the output:
- `metrics.csv` with one row per variant, plus aggregate rows (expectancy mean ± CI, gap-through rate ± CI, gap-through magnitude mean ± CI, signal volume) per variant.
- `run_manifest.json` with all V2.1 §IV.C fields populated.

**Acceptance:**
- Run completes without error.
- Output files exist with expected fields.
- Plausibility checks: signal counts nonneg, expectancy finite, gap-through rate ∈ [0,1].
- The `full-run-out/` directory was either gitignored by 2b's `.gitignore` entry (intended) or you explicitly stage it for commit. Per V2.1 §IV.C provenance, the raw outputs SHOULD be committed (small CSV + JSON).

**Modify `.gitignore` if necessary** to UN-ignore the full-run output (the smoke-out was gitignored to avoid committing throwaway shape-checks; the full-run is the substantive evidence and should be tracked). Either:
- Move `full-run-out/` to a tracked location (e.g., `research/studies/earnings-proximity-exclusion-results-data/`), or
- Add a specific `!full-run-out/` exception to the gitignore.

**D3 commit message:**

```
data(research): full-window earnings-proximity-exclusion study run results

5 variants × <N> tickers × <M> trading days. Metrics and provenance
manifest committed for evidence-summary review (D4). Per V2.1 §IV.C
research provenance requirements.
```

Adjust the placeholder counts to actuals.

### D4 — Evidence summary writeup

This is the substantive analysis work. Open the pre-registered `earnings-proximity-exclusion-results.md` and:

1. **Fill in the §"Observed results"** with the variant-by-variant metrics from `metrics.csv`, including confidence intervals per the pre-registered framework.
2. **Apply pre-registered thresholds** to assign a tier per metric. Document the mapping explicitly: which observed value maps to which tier. If different metrics map to different tiers (e.g., expectancy strong but gap-through-rate moderate), document the conflict and resolve per a pre-registered rule (or, if the rule wasn't pre-registered, document the resolution method honestly — this is a known weakness).
3. **Compute survivorship-bias caveats per protocol.** Apply the protocol's Metric Treatment subsection to every reported number. Absolute metrics get "survivorship-biased lower bound" annotations; relative metrics get "magnitude likely understated" notes.
4. **Final decision** in the §"Decision" section: one of `reject` / `shadow` / `promote` (with chosen X) / `defer`. Cite the tier assignment that produced it. Cite the protocol.
5. **Discussion** section covering all three biases (survivorship, fixed-universe, universe-staleness), open issues, sample-size limits, calendar-source-reliability caveats (sample-size 7 effective from Session 2a), and any methodology concerns surfaced during analysis.

**Acceptance:**
- All pre-registered checkboxes filled (`[x]` for confirmations or explicit deviation explanations).
- Every numeric in the document is caveated per protocol.
- Tier assignment is internally consistent.
- Decision is one of the four tiers, named explicitly.
- Discussion includes ALL three named biases.

**D4 commit message:**

```
docs(research): evidence summary, tier assignment, and decision for earnings-proximity-exclusion

Decision: <reject | shadow | promote (X=N) | defer>

Tier assignment:
- <metric>: <observed> → <tier>
- <metric>: <observed> → <tier>
...

Citations: study design's Survivorship-bias interpretation protocol;
pre-registered thresholds in this document's §"Pre-registration"
(commit <D1-SHA>); raw outputs in metrics.csv from <D3-SHA>.
```

### D5 — Adversarial review on statistical conclusions

**This is the first session where adversarial review targets statistical conclusions, not code.** The Codex prompt and review focus differ from prior sessions.

#### Review prompt — adapt and use

Use a prompt approximating this shape when invoking `copowers:adversarial-critic` or running Codex MCP directly:

> "Review this evidence-summary document for a research study using a synthetic-replay backtest of an earnings-proximity exclusion rule. The document is the research output, not code. Focus your review on:
> 
> 1. Whether the pre-registered thresholds (§Pre-registration) are objective and pre-data, or whether they show signs of post-hoc tuning.
> 2. Whether the observed-to-tier mapping (§Tier assignment) faithfully applies the pre-registered thresholds, or whether the assignment was bent toward a desired conclusion.
> 3. Whether the survivorship-bias protocol's caveats (absolute vs relative metric treatment per the study design) are correctly applied to every reported number.
> 4. Whether the statistical-inference framework (CIs / p-values / multiple-comparison correction) is internally consistent and appropriate for the reported sample size.
> 5. Whether the decision (reject / shadow / promote / defer) is justified by the tier assignment with no leakage of the analyst's prior preference.
> 6. Whether the discussion section covers all three known biases (survivorship, fixed-universe, universe-staleness) AND the calendar-source-reliability caveat (sample size 7 effective).
> 7. Whether the sensitivity checks pre-registered for promoted variants were actually performed and reported, OR whether their absence is acknowledged.
> 8. Whether `defer` is correctly invoked for weak/null signals per the protocol's anti-rationalization rule, OR whether such signals were rationalized into `reject` or `shadow`.
> 9. Whether any numerical result is reported without a confidence interval, sample size note, or appropriate uncertainty annotation.
> 10. Whether the document's framing exhibits any of: confirmation bias, anchoring on the pre-registered thresholds in a self-fulfilling way, garden-of-forking-paths reasoning, or HARK-ing (hypothesizing after results known)."

Iterate rounds (MIN=2, MAX=5 per plugin defaults) until `NO_NEW_CRITICAL_MAJOR`.

**Watch items the reviewer is likely to probe:**
- Suspiciously round threshold numbers (suggests post-hoc tuning to land on a tier the analyst wanted).
- Tier conflicts between metrics resolved by analyst-judgment without pre-registered conflict-resolution rule.
- Ignored sensitivity checks ("we said we'd check X, then didn't").
- Confidence-interval omissions on key absolute numbers.
- Implicit dropping of `defer` from consideration when results are weak.
- Survivorship-bias caveats that are footnoted away from the headline numbers.
- Sample-size-vs-power mismatches (claiming `promote` from a sample where the CI on the effect is wide enough to include null).

#### Acceptance for D5

- Review rounds complete with `NO_NEW_CRITICAL_MAJOR`.
- All review findings either FIXED in D6 or ACCEPTED-with-rationale (with the rationale documented in the return report and, if substantive, also in the evidence summary's Discussion).
- The decision tier is unchanged by adversarial review IF the methodology is sound, OR is changed (e.g., promote → shadow, or shadow → defer) IF review surfaces a methodology flaw that requires retreat.

If review changes the decision: the original decision and the change are BOTH documented in the evidence summary, with citation to the review finding that drove the change.

### D6 — Review-fix commit (if needed)

Standard pattern: fix findings in a new commit, no amending. Add tests if any code was touched (likely none). Update the evidence-summary content to reflect any tier or decision change.

Commit message pattern:

```
fix(research): address session-2c adversarial-review findings

<numbered list of findings + resolutions>

Review thread ID: <Codex MCP thread ID>
Final verdict: NO_NEW_CRITICAL_MAJOR at Round <N>
```

---

## 4. Adversarial review framing — different from prior sessions

Prior code-shipping sessions (Tranche A, B-ops, B-research-2b) had Codex review **code+test diffs**: API misuse, boundary conditions, bug introductions, regression-test adequacy. Those reviewers were probing for execution defects.

**This session's reviewer probes for METHODOLOGICAL defects in research output.** The defects look different:

| Code-review failure | Methodology-review failure |
|---|---|
| Missing test for boundary case | Missing pre-registered threshold for boundary case |
| Off-by-one in loop | Off-by-one in degrees of freedom (e.g., paired vs unpaired) |
| Silent exception swallowing | Silent omission of an inconvenient subset (e.g., 2024 didn't work but 2025 did → only reporting "across 2024-2025") |
| Variable shadowing | Definition shifting (e.g., redefining "gap-through" mid-analysis to fit observed data) |
| Unclear naming | Unclear / shifting null hypothesis |
| Hardcoded values | Threshold-tuning to hit a desired tier |

The reviewer's job is to model the analyst as an adversary who would (consciously or not) select methodology choices that push the conclusion toward what they wanted to find. The analyst's job is to defend the methodology against that scrutiny.

**Pre-registration is the structural defense against most of these failures.** D5's review primarily verifies that pre-registration was honored, not that thresholds were "right" in some objective sense. If the analyst pre-registered a threshold that turns out to map their data to `defer`, that's a successful study, not a failure to fix.

---

## 5. Binding conventions

- **Branch:** `main`.
- **Commits:** conventional-commits. `docs(research):`, `data(research):`, `feat(research):` for any code, `fix(research):` for review fixes. **No Claude co-author footer. No `--no-verify`. No amending.**
- **TDD:** any harness code touched gets red-green-refactor. Most of this session is execution + analysis; minimal new code is expected.
- **Tests:** fast suite green after every commit. Baseline going in: 623.
- **Ruff:** no new violations beyond the 81-error baseline.
- **Phase isolation:** `swing/*` is consumed read-only. No DB writes. The harness runs against the `research-cache/` directory under `%USERPROFILE%/swing-data/`, not against `swing.db`.

---

## 6. Done criteria

- D0 + D1 + D3 + D4 + D5 + (D6 if needed) all shipped (D2 is a cache state change; commit only if code was touched).
- Pre-registration commit (D1) precedes study-run commit (D3) in `git log`.
- Adversarial review verdict: `NO_NEW_CRITICAL_MAJOR`.
- Evidence summary has a final decision: one of `reject` / `shadow` / `promote` (with chosen X) / `defer`.
- Decision is justified by tier assignment, which is justified by pre-registered thresholds applied to observed values.
- All three biases (survivorship, fixed-universe, universe-staleness) disclosed in the discussion section.
- Sensitivity checks performed if pre-registered.
- Fast suite green; no new ruff violations.
- Return report produced.

---

## 7. Return report format

```
## Tranche B-research session 2c return report

### Split status
<"Not invoked." OR "Invoked — 2c-a shipped D0–D3; 2c-b continuation required for D4–D6.">

### Commits landed
- <SHA> docs: track session-2c dispatch brief                                             (D0)
- <SHA> docs(research): pre-register tier thresholds for earnings-proximity analysis      (D1)
- <SHA> feat(research): <harness tweak if any>                                            (D2 — only if code touched)
- <SHA> data(research): full-window earnings-proximity-exclusion study run results        (D3)
- <SHA> docs(research): evidence summary, tier assignment, and decision                   (D4)
- <SHA> fix(research): address session-2c adversarial-review findings                     (D6 — if needed)

### Pre-registration discipline
- Pre-registration commit SHA: <D1>
- Study run commit SHA: <D3>
- Confirmed: D1 precedes D3 in git log.

### Tests
- Before: 623 passing, 0 failing.
- After: <N> passing, 0 failing. New tests: <M>. (May be 0 if no code changes.)

### Cache state after session
- OHLCV: <N> tickers cached, <MB> total.
- Earnings: <N> tickers cached, <MB> total.
- Window: <YYYY-MM-DD> to <YYYY-MM-DD>.

### Study results — top-level
- Universe: <N> tickers, version-hash <hash>.
- Trading days: <N>.
- Total signals across variants: <N>.
- Per-variant signal counts: X=0 → <N>; X=3 → <N>; X=5 → <N>; X=7 → <N>; X=10 → <N>.
- Sample-size estimate from D1: <pre-registered>.
- Sample-size observed: <D3 actual>.
- Sample-size-estimate error: <%>.

### Decision
**<reject | shadow | promote (X=N) | defer>**

Citation: <evidence summary §Decision SHA>; tier mapping cites observed values from <D3 SHA>; pre-registered thresholds in <D1 SHA>.

### Tier assignment per metric
| Metric | Observed | Pre-reg threshold tier | Tier assigned |
|---|---|---|---|
| ... | ... | ... | ... |

### Adversarial review — summary
- Rounds: <N>
- Base SHA: <D0 or D3 SHA depending on what was reviewed>
- Thread ID: <Codex MCP>
- Findings: <N> critical / <N> major / <N> minor
- FIXED: <short summary>
- ACCEPTED-with-rationale: <short summary>
- Decision-changing findings: <yes/no; if yes, original→final>
- Verdict: NO_NEW_CRITICAL_MAJOR at Round <N>

### Survivorship-bias protocol — compliance
- [x] Absolute metrics caveated as "survivorship-biased lower bound" — yes/no
- [x] Relative metrics noted as "magnitude likely understated" — yes/no
- [x] All three biases disclosed (survivorship, fixed-universe, universe-staleness) — yes/no
- [x] Calendar-source sample-size caveat (7 effective) disclosed — yes/no
- [x] Anti-rationalization clause honored (weak/null → defer) — yes/no
- [x] Sensitivity checks per pre-registration performed — yes/no/n-a-because-not-promoted

### Deviations from brief / spec
<empty if none>

### Items flagged but not done (scope discipline)
<bullets>

### Open questions for orchestrator
<bullets>
```

---

## 8. If you get stuck

- If pre-registration feels like guessing, that's because it is — pre-registration is a discipline mechanism, not a precision tool. Pick concrete numbers based on the sample-size estimate and the protocol's qualitative tier descriptions. The reviewer will probe whether they're objective; defensible-and-pre-data beats clever-and-post-data.
- If observed results land cleanly in one tier per all metrics, the analysis is easy. If they straddle tiers (e.g., expectancy says strong but signal-volume says reject), the brief explicitly flags this — document the conflict, resolve per pre-registered rule if available, otherwise document the resolution method honestly.
- If the cache warm-up exceeds 90 minutes, invoke the split contingency. Don't burn through D4 on session fatigue.
- If a metric you pre-registered turns out to be uncomputable from the actual data shape, document the gap in the evidence summary's "Open issues" section and proceed with the available metrics. Do NOT silently drop a pre-registered metric.
- If the decision is `defer` and you feel the urge to soften it ("but the trend is positive..."), STOP. Defer is not a failure; it's the correct outcome when survivorship bias prevents distinguishing weak-effect from no-effect. The protocol's anti-rationalization clause is binding.
- If the decision is `promote` and you feel pressure to caveat it into shadow ("just to be safe..."), also STOP. Pre-registered strong-signal thresholds plus survivorship-bias-aware interpretation already make `promote` conservative. Soft-pedaling a pre-registered strong signal is the same failure mode as rationalizing a weak signal upward — both deviate from the pre-registered protocol.
- If adversarial review changes the decision, that is normal and expected. The whole point of adversarial review is to catch the cases where the analyst's framing was wrong. Update the evidence summary, document the change, ship the corrected decision.
