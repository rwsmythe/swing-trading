# S&P 1500 Universe Expansion Study — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Test whether expanding the production universe from SPX+NDX (~516 tickers) to the S&P 1500 (~1,500 tickers — adds the S&P MidCap 400 and SmallCap 600) produces a meaningful A+ rate uplift at the operator's actual 1× capital, with manageable data-quality and liquidity profile. Pre-register decision tiers BEFORE viewing data. Descriptive only — no production-code recommendations.
**Expected duration:** ~1 session (3–5 hours).
**Prepared:** 2026-04-25 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions (conventional commits, no-amend, no `--no-verify`, no Claude co-author footer, Phase isolation). Note: research code lives at `research/`; consumes `swing/` read-only.
2. `docs/orchestrator-context.md` — particularly §"Recent decisions and framings" (capital-sensitivity disposition, three-branch architecture, hypothesis 5 closed, path-1 selected for residual gap), §"Anti-patterns to avoid" (mid-session scope expansion, treating "diagnose, don't decide" as soft, vacuous regression tests, manifest-integrity), §"Lessons captured" (production-gating-aware instrumentation, manifest-integrity generalization, n=1 sample bounds claims).
3. `research/studies/candidate-sparsity-diagnostic.md` — the immediate predecessor study. Establishes the universe-variant comparison methodology this study extends. §"Methodology" §"Universes" describes how SPX+NDX and Russell 3000 were loaded; this study adds S&P 1500 as a third variant. §"Caveats and limitations" — particularly the survivorship-bias and fixed-universe-snapshot caveats apply identically here.
4. `research/studies/harness-vs-production-parity.md` — establishes the discipline pattern (D1 → D2 → D3 → D4 → D5+) you'll mirror.
5. `research/harness/earnings_proximity/universe_variants.py` — the existing universe-variant loader. You'll add an `sp1500` loader following the same pattern as the IWV (Russell 3000) loader. Read end-to-end to understand the loader contract.
6. `research/harness/earnings_proximity/instrumented_replay.py` — per-criterion logging wrapper. Reused unchanged.
7. `research/harness/earnings_proximity/run.py` and (if present) `research/harness/earnings_proximity/scripts/diagnostic_run.py` — the diagnostic driver pattern. You'll extend this (or write a parallel driver) to include the new S&P 1500 universe variant.
8. `research/harness/earnings_proximity/scripts/recompute_binding_prod_gated.py` — the production-gated blocker recomputation. Reused unchanged for the new run.

**Skill posture.**
- DO invoke `superpowers:verification-before-completion` before declaring done.
- DO invoke `copowers:adversarial-critic` after the findings-writeup commit lands. Standing convention; iterate to `NO_NEW_CRITICAL_MAJOR`. Adversarial review here matters — instrumentation honesty (manifest provenance, production-gating awareness) is a recurring class of finding.
- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans` — scope is fully specified by this brief.

---

## 1. Strategic context (compressed)

The candidate-sparsity diagnostic (Tranche C, 2026-04-25) measured A+ rate per ticker-day across 4 universe×capital cells:

| Cell | Rate per ticker-day | A+ count over 504 sessions |
|---|---|---|
| SPX+NDX 1× ($7,500) | 0.00193% | 5 |
| SPX+NDX 5× ($37,500) | 0.00387% | 10 |
| Russell 3000 1× | 0.00890% | 112 |
| Russell 3000 5× | 0.00977% | 123 |

Russell 3000 produced ~22× more A+ candidates than SPX+NDX at constant 1× capital. **But the diagnostic documented serious data-quality problems with Russell:** 54% of Russell A+ signals carried `absent_earnings_data=True` (yfinance coverage gaps for small/mid-caps), survivorship bias is materially worse for small-caps, liquidity for many names is below tradable thresholds, and 14 Russell tickers failed yfinance OHLCV lookup entirely. A naive Russell adoption would import all those problems into production.

**S&P 1500 is the measured middle ground.** It adds the S&P MidCap 400 + S&P SmallCap 600 to the existing SPX 500 (≈1,500 tickers, ~3× current SPX+NDX size). Avoids the worst microcap problems while plausibly producing somewhere between 2× and 4× the SPX+NDX rate (extrapolating along the SPX→Russell gradient). This study verifies the rate uplift AND characterizes the data-quality / liquidity profile on this specific universe at the operator's actual 1× capital.

**Operationally, the question is whether the lever is real.** The operator currently sees ~2 A+/year in production. Even a 2-3× uplift translates to 4-6 A+/year — the difference between barely operating and operating with weekly cadence. Combined with capital constraints (operator's 1× is binding), universe is the cleanest available rate-uplift lever absent compromising the strategy's edge claim (threshold relaxation is anti-pattern).

**This study scopes to S&P 1500 only.** It is NOT a comparison of every plausible universe variant; it is a focused test of a specific candidate. Findings are descriptive; the operator decides whether to act.

---

## 2. Scope — single-universe study at operator's 1× capital

### In scope

- Add an `sp1500` universe variant under `research/harness/earnings_proximity/universe_variants.py` (or equivalent location), following the same pattern as the existing IWV (Russell 3000) loader.
- Source: combine iShares S&P 500 (`IVV`), S&P MidCap 400 (`IJH`), and S&P SmallCap 600 (`IJR`) holdings CSVs from the iShares CDN (same pattern as IWV fetch). Dedupe across the three lists; filter to `Asset Class == 'Equity'`.
- Run the diagnostic at one cell only: `sp1500 × 1× capital ($7,500)`. Same 504-session window as the diagnostic (2024-04-19 → 2026-04-23), cache-warm.
- Pre-registration commit (D1) with frozen tier thresholds.
- Implementation commit (D2) with the new loader + extension to the diagnostic driver.
- Run commit (D3) with the run artifacts.
- Findings writeup commit (D4) — `research/studies/sp1500-universe-expansion.md` with results, tier classification, sector breakdown, data-quality characterization, liquidity distribution.
- Adversarial-review fix commits (D5+) as needed.

### Out of scope

- Any other universe variant (e.g., S&P 1500 ETF-direct via ITOT, MSCI USA Investable Market, Wilshire 5000). If the data shows S&P 1500 is borderline and another variant would be informative, FLAG in the return report — do NOT silently expand.
- 5× capital cell on S&P 1500. Operator deferred capital-driven workflow changes (per `docs/orchestrator-context.md` §"Recent decisions" 2026-04-25); 1× is the operationally relevant cell.
- Any production-code change (Phase 2 carve-out NOT granted).
- Any prescription. This study is descriptive: tier classification + open questions, not "switch to S&P 1500" or similar recommendation.
- Trade-outcome simulation. The harness's `simulate_trade` is NOT invoked. This study measures rate, not edge. (Consistent with candidate-sparsity diagnostic scope.)
- Multi-window characterization. Single 504-session window only; regime variation is a separate question (hypothesis 4, deferred).

---

## 3. Binding conventions

- **Branch:** `main`. No feature branch.
- **Commits:** conventional. **No Claude co-author footer. No `--no-verify`. No amending.**
- **TDD:** failing test first → see fail → minimal implementation → see pass → commit, per logical change.
- **Tests:** `python -m pytest -m "not slow" -q` must stay green. Current baseline 755 passing on `main` (per `2e620c3`). Your new tests under `tests/research/harness/` should add to this count.
- **Phase isolation:** Touch `research/` only. No carve-out for `swing/`. Read `swing/` modules; do not modify them.
- **Pre-registration discipline:** D1 commit (study doc with thresholds) MUST land BEFORE D3 (data run). Anti-rationalization clause: tier boundaries frozen at D1; D5 adversarial-review fixes can clarify framing but cannot move tier boundaries.

---

## 4. Pre-registration (D1)

Create `research/studies/sp1500-universe-expansion.md`. Commit with message `docs(research): pre-registration commit — S&P 1500 universe expansion study`. The pre-registration MUST contain:

### Hypothesis statement

> Expanding the harness universe from SPX+NDX (~516 tickers) to the S&P Composite 1500 (~1,500 tickers — combining iShares IVV, IJH, IJR holdings) produces a meaningful A+ rate uplift at the operator's actual 1× capital, with manageable data-quality and liquidity profile.

### Pre-registered decision tiers (frozen at D1)

Computed across all (ticker, date) evaluations in the S&P 1500 1× run, compared against the diagnostic's existing SPX+NDX 1× baseline (5 A+ over 260,064 ticker-days = 0.00193% per ticker-day).

- **Tier 1 — Adopt-candidate.** A+ rate uplift ≥3× SPX+NDX baseline (i.e., ≥0.0058% per ticker-day on S&P 1500) AND <30% of A+ signals carry `absent_earnings_data=True`. Interpretation: S&P 1500 is a viable production-universe candidate; warrants operator decision on whether to switch and over what cadence (immediate, A/B comparison, etc.). Study findings include sector + liquidity characterization to inform that decision.

- **Tier 2 — Mixed.** A+ rate uplift ≥2× but <3× SPX+NDX baseline OR ≥3× rate uplift but with ≥30% absent earnings data OR rate uplift in the 2–3× range with concerning sector concentration (defined: any single sector accounts for ≥40% of A+ signals). Interpretation: meaningful uplift exists but at observable cost; operator decides whether tradeoff is acceptable for their workflow.

- **Tier 3 — Not viable.** A+ rate uplift <2× SPX+NDX baseline. Interpretation: S&P 1500 expansion doesn't deliver enough rate uplift to justify the noise of a larger universe. SPX+NDX remains the operational universe.

### Anti-rationalization clause

The tier boundaries (3×/2× rate uplift; 30% earnings absence; 40% sector concentration) are frozen at D1. If post-data results sit near a boundary (e.g., 2.95× rate uplift with 28% earnings absence), the result IS what the frozen boundaries say it is; no boundary adjustment to push it across. Findings writeup may discuss the proximity but the classification is what it is.

### Liquidity profile reporting (descriptive, not gating)

The study reports the avg daily $ volume distribution for A+ signals (median, 25th percentile, fraction below $500K/day). At the operator's 1× capital ($7,500 with ~10% position size ≈ $750 trade), liquidity is unlikely to be a binding constraint, so this is descriptive — the operator can read the distribution and decide whether any execution-difficulty concerns warrant attention.

### Sample-size limitation

Single 504-session window on S&P 1500 produces a single observation of the rate. For tighter inference, a multi-window or rolling-window characterization would be the named follow-on. The study's tier classification on this sample is descriptive of THIS WINDOW; it does NOT establish the rate stable across regimes.

### Surfaces explicitly NOT measured

- Trade outcomes (expectancy, win rate, gap-through statistics). The harness's `simulate_trade` is not invoked.
- Universe membership drift (S&P 1500 reconstitution timing; the snapshot is fixed at fetch date).
- Sector classification accuracy (uses iShares' reported sector field; may differ from production's GICS or other source).
- Pattern shape distribution among A+ signals (no flag/cup-with-handle/flat-base classifier in the harness yet; reference to `docs/phase3e-todo.md` §3e.6).

### Provenance commitments

The D3 run manifest will record:
- Harness git SHA (post-D2 commit).
- Universe metadata: source URLs (3 iShares CDN URLs), fetch date, per-ETF ticker counts, post-dedupe ticker count, post-equity-filter ticker count, SHA-256 of the combined universe CSV.
- Capital: $7,500 (operator's `max(starting_equity, risk_equity_floor)`).
- Window: 2024-04-19 → 2026-04-23 (504 NYSE sessions).
- Cache stats: yfinance OHLCV hits/misses; earnings hits/misses.
- A+ count, evaluation count, per-criterion production-gated blocker counts.
- Sector breakdown of A+ signals.
- Liquidity distribution of A+ signals.

### Run procedure (locked by pre-registration)

1. After D2 lands and tests pass, run the diagnostic-style driver against `sp1500 × 1×`.
2. Inspect output WITHOUT computing tier classification first — verify the run completed without errors, manifest is written, output schema is correct, cache hit rates are reasonable.
3. Compute tier classification per the frozen thresholds.
4. Write D4 findings doc; do NOT modify D1 thresholds.

---

## 5. Implementation (D2)

### 5.1 Loader

Add an `sp1500` variant to the existing universe-variant loader (`research/harness/earnings_proximity/universe_variants.py`). Source pattern mirrors IWV:

- Fetch holdings CSVs from iShares CDN for IVV, IJH, IJR (URLs: search `https://www.ishares.com/us/products/<id>/<slug>/<id>.ajax?fileType=csv&fileName=...` — operator can verify by visiting each ETF's product page on ishares.com and copying the "Download Holdings CSV" link).
- Parse each CSV: skip header rows, locate the data rows, extract `Ticker`, `Asset Class`, `Sector`, plus optional fields (`Market Cap`, `Average Daily Volume` if present in the iShares CSV).
- Filter to `Asset Class == 'Equity'`.
- Dedupe across the three lists by ticker (no overlap expected by index construction, but dedupe defensively).
- Cache the combined universe CSV to `~/swing-data/research-cache/universe-snapshots/sp1500_<YYYY-MM-DD>.csv`.
- Compute SHA-256 of the combined CSV; record in manifest.

If iShares URLs are not directly known to the implementer, document the URL discovery process in the run manifest's `notes` field so the study is reproducible.

### 5.2 Driver extension

Extend the existing diagnostic driver (or add a parallel driver under `research/harness/earnings_proximity/scripts/`) to support running a single `sp1500 × 1×` cell. The infrastructure is already in place (universe variants, capital multiplier, instrumented replay); this is a configuration extension, not a new pipeline.

### 5.3 Test discipline

- `tests/research/harness/test_universe_variants.py` (extend existing): one new test for the `sp1500` loader. Mock the three iShares CSV fetches; verify dedupe, equity filter, expected ticker count (≈1,500 ± 50 — exact will depend on snapshot date).
- `tests/research/harness/test_diagnostic_driver.py` (extend or new): smoke test for the `sp1500 × 1×` cell. Mocked OHLCV; verify the run completes, manifest is written, cell parameters are correctly threaded.

Total expected new tests: ~4–6. Fast suite should grow from 755 to 759–761.

### 5.4 Implementation commit shape

Commit body:
```
feat(research): S&P 1500 universe variant for sparsity study (D2)

Adds sp1500 loader to research/harness/earnings_proximity/
universe_variants.py — combines iShares IVV + IJH + IJR holdings
(SPX 500 + MidCap 400 + SmallCap 600). Same pattern as IWV loader
for Russell 3000.

Driver extension supports single-cell sp1500 × 1× run.
Pre-registration discipline established in
research/studies/sp1500-universe-expansion.md (D1).

Phase isolation: research/ only. No swing/ modifications.
```

---

## 6. Run (D3)

After D2 lands and tests pass:

1. Verify the iShares CDN endpoints are reachable; download the three holdings CSVs (loader handles this).
2. Verify yfinance cache covers most S&P 1500 tickers — many SPX+NDX overlap is already cached; mid-cap and small-cap will need fresh fetches. Expected ~1,000 cold OHLCV fetches + ~1,000 cold earnings fetches; budget time accordingly (~30–60 min depending on yfinance throughput).
3. Run the diagnostic driver:
   ```bash
   python -m research.harness.earnings_proximity.scripts.diagnostic_run \
       --universe sp1500 \
       --capital-multiplier 1.0 \
       --output-dir research/harness/earnings_proximity/diagnostic-out/run_E_sp1500_1x/
   ```
   (Adjust CLI form to match the actual driver interface.)
4. Inspect output structure (file listing, manifest content, evaluations.csv schema). Do NOT compute or interpret tier classification yet; that's D4.
5. Commit the run artifacts:
   ```
   data(research): S&P 1500 universe expansion study run (D3)

   Run output for the S&P 1500 × 1× cell. Pre-registration:
   research/studies/sp1500-universe-expansion.md (D1).

   Tier classification deferred to D4 findings doc.
   ```

`evaluations.csv` is large (~30–80 MB given S&P 1500 size); add to `.gitignore` per the candidate-sparsity diagnostic convention. Manifest, A+ signals CSV, binding-constraint CSVs commit normally.

---

## 7. Findings writeup (D4)

Update `research/studies/sp1500-universe-expansion.md`. Append (do NOT modify D1's pre-registration sections — they are frozen):

- §"Run details" — universe metadata (per-ETF ticker counts; combined post-dedupe count; equity-filter survivor count), window, capital, harness git SHA, cache stats.
- §"Results — rate" — A+ count, evaluation count, rate per ticker-day, rate uplift vs SPX+NDX 1× baseline, Wilson 95% CI on the new rate.
- §"Results — per-criterion binding constraints (production-gated)" — full production-gated blocker table per the candidate-sparsity diagnostic format.
- §"Results — sector breakdown of A+ signals" — table of A+ count by sector; concentration ratio; comparison to S&P 1500 sector composition (so reader can see whether A+ signals over- or under-index any sector).
- §"Results — liquidity distribution of A+ signals" — avg daily $ volume distribution: median, 25th/75th percentile, fraction below $500K/day, fraction below $1M/day.
- §"Results — data-quality characterization" — fraction of A+ signals with absent earnings data; fraction of universe with yfinance OHLCV-fetch failures; any other coverage observations.
- §"Tier classification" — apply D1's frozen thresholds; state the resulting tier directly.
- §"Findings (descriptive, not prescriptive)" — 4–8 numbered findings; mirror the descriptive style of `research/studies/candidate-sparsity-diagnostic.md` §"Findings."
- §"What this study does NOT say" — at minimum: does not test trade outcomes; does not test alternative universe variants; does not establish rate stability across regimes (single window); does not recommend production change.
- §"Caveats and limitations" — at minimum: single-window sample; survivorship bias inheritance; iShares-snapshot-derived (not point-in-time S&P composite); yfinance coverage variability across cap tiers.
- §"Open questions for the operator" — phrased as questions, not recommendations. Examples: "Does the tier classification cross your threshold for adopting S&P 1500 as the production universe?"; "If sector concentration is high, does any of the over-represented sectors raise exposure concerns?"; "If liquidity distribution shows a long tail of low-volume A+ signals, would you want to filter at production-ingest time or accept and decide per-candidate?"

Commit:
```
docs(research): S&P 1500 universe expansion findings (D4)

Tier <N> result on S&P 1500 × 1× cell. <Headline summary of rate
uplift, data quality, sector concentration>. Findings descriptive
only; open questions to operator.
```

---

## 8. Adversarial review (D5+)

After D4 lands, invoke `copowers:adversarial-critic` on the combined diff (D2 + D3 + D4). Iterate to `NO_NEW_CRITICAL_MAJOR`. **Specific watch items** (paste these into your invocation):

- **Manifest integrity (parity-check R1 lesson).** Verify `harness_git_sha` in the D3 manifest reflects the actual code state at run time, NOT the most-recent commit when the artifact was committed. If you edited the loader during the run window with uncommitted changes, the manifest is wrong; fix in a new commit with byte-identical re-run.
- **Production-gating-aware blocker computation (candidate-sparsity diagnostic R1 Critical lesson).** The per-criterion binding-constraint table MUST use `recompute_binding_prod_gated.py` semantics (production gating order: `risk_feasibility` hard filter → trend-template gate → VCP-fail count). Do NOT report emitted-order counts as the primary metric. Verify against the candidate-sparsity diagnostic report's same structure.
- **Universe loader provenance.** Verify the three iShares CSVs were fetched on the same date; record fetch date per CSV. If iShares published an update mid-fetch, the universe is internally inconsistent — flag.
- **Anti-rationalization compliance.** Verify D4's tier classification used D1's exact thresholds. Search the writeup for boundary-shifting language ("just barely meets," "essentially Tier 1") that effectively moves a near-boundary case.
- **Descriptive-not-prescriptive compliance.** Search for "should," "recommend," "must" used as prescriptive direction. Each instance is a candidate violation; reframe as descriptive or move to the open-questions section.
- **Sample-size framing.** Verify the writeup does not over-claim. Single window is descriptive of one window, not the rate stable across regimes.
- **Liquidity distribution descriptive vs gating compliance.** D1 specified liquidity is descriptive, not gating. Verify D4 doesn't smuggle in implicit gating language ("only X% are tradable" implies a gate).
- **Capital-sensitivity disposition compliance.** D1 scoped this to 1× only. Verify D4 doesn't re-litigate the 5× capital question or introduce 5× findings.

Fix any major-severity findings in NEW commits per no-amend rule. Minor findings either fix in same follow-up or `ACCEPT-with-rationale`.

---

## 9. Done criteria

- D1 commit (pre-registration) landed BEFORE D3 (run). `git log` order verifies.
- D2 commit (loader + driver extension + tests) landed; tests pass.
- D3 commit (run artifacts) landed; manifest + per-criterion + sector + liquidity outputs present.
- D4 commit (findings writeup) landed; tier classification applied to D1's frozen thresholds.
- D5+ adversarial-review pass landed (separate commit per fix, no amend); verdict `NO_NEW_CRITICAL_MAJOR`.
- Fast suite green: 759+ passing (755 baseline + ~4+ new tests).
- No `swing/` modifications. No production DB modifications.
- Return report produced per §10.

---

## 10. Return report format

```
## S&P 1500 universe expansion study — return report

### Commits landed
- <SHA1> docs(research): pre-registration commit — S&P 1500 universe expansion study (D1)
- <SHA2> feat(research): S&P 1500 universe variant for sparsity study (D2)
- <SHA3> data(research): S&P 1500 universe expansion study run (D3)
- <SHA4> docs(research): S&P 1500 universe expansion findings (D4)
- <SHA5+> (if any) fix(research): address adversarial review finding(s)

### Run details
- Universe: sp1500 (post-dedupe equity count: <N>)
- iShares fetch date: <YYYY-MM-DD>
- Window: 2024-04-19 → 2026-04-23 (504 NYSE sessions)
- Capital: $7,500 (1×)
- Harness git SHA at run: <SHA>

### Results
- A+ count: <count>
- Evaluation count: <count>
- A+ rate per ticker-day: <rate>%
- Rate uplift vs SPX+NDX 1× baseline: <multiplier>×
- Absent earnings data fraction: <fraction>%
- Sector concentration (largest single sector): <sector> at <fraction>%
- Liquidity (median A+ avg daily $ vol): $<amount>
- Tier classification: <Tier 1 | Tier 2 | Tier 3>

### Tests
- Before: 755 passing (baseline from 2e620c3)
- After: <N> passing, 0 failing. New tests: <count>.

### Adversarial review verdict
- <NO_NEW_CRITICAL_MAJOR | findings summary if any>

### Deviations from brief
- <Empty if none. List any judgment calls and their rationale, especially for ambiguities in iShares URL discovery or driver-interface specifics.>

### Open questions for orchestrator
- <Empty if none.>
```

---

## 11. If you get stuck

- **If iShares CDN URLs are not directly discoverable** (URLs sometimes change): document the discovery process in the manifest `notes` field. As a fallback, the operator can manually download the three CSVs from ishares.com and place them at a known path; brief the implementer on the fallback location.
- **If yfinance fetches fail at scale on the new MidCap/SmallCap names**: skip those tickers in the run (they contribute neither to numerator nor denominator); list them in the manifest. Do not fail the whole run. Document the failure rate; this is a data-quality observation that feeds the tier classification.
- **If the rate comes out at exactly Tier 1 with very high uplift (e.g., ≥10×)**, sanity-check the loader didn't accidentally include non-equity rows (treasuries, cash collateral) that would inflate the universe denominator without contributing to the numerator. The IWV loader for Russell 3000 specifically filters `Asset Class == 'Equity'`; verify the same filter applies to all three iShares CSVs.
- **If the rate comes out at exactly Tier 3 with very low uplift (e.g., <1.5×)**, sanity-check that the harness BatchContext universe is set to S&P 1500 (so RS rank is computed against the larger pool), not silently retained as SPX+NDX from the diagnostic's previous configuration.
- **If sector classification differs systematically between iShares' reported sector and what production uses for any operator-facing display**: flag in return report. Production may use GICS or a different taxonomy; the writeup's sector breakdown should be transparent about which taxonomy it uses.
- **If pre-registration discipline is accidentally broken** (e.g., you ran D3 before committing D1): the study is no longer pre-registered. Do not try to hide this; document explicitly in the writeup that D1's "pre-registration" was post-hoc. The operator can decide whether to discard the run and redo, or accept the loss of pre-registration as a study limitation.
