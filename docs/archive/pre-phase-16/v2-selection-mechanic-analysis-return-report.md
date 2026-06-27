# V2-Selection-Mechanic Analysis -- Return Report

**Dispatch brief:** [`docs/v2-selection-mechanic-investigation-dispatch-brief.md`](v2-selection-mechanic-investigation-dispatch-brief.md) (baseline `55d0f48`)
**Investigation branch:** `applied-research-v2-selection-mechanic-investigation`
**HEAD at return:** `<post-slice-8-commit>` (this commit)
**Study writeup (primary):** [`research/studies/2026-05-26-v2-selection-mechanic-analysis.md`](../research/studies/2026-05-26-v2-selection-mechanic-analysis.md)
**Findings doc:** [`docs/v2-selection-mechanic-analysis-findings-2026-05-26.md`](v2-selection-mechanic-analysis-findings-2026-05-26.md)
**Smoke artifact:** [`exports/research/v2-selection-mechanic-analysis-20260527T084319Z/`](../exports/research/v2-selection-mechanic-analysis-20260527T084319Z/)

---

## Sec 1 Mission Summary

ANALYTICAL / EXPLORATORY investigation (NOT a backtest) of the cumulative cross-cohort finding that V2-binding-variable cohort selection produces W-pattern-thin substrates. For each of the 5 V2 OHLCV binding variables identified in the V2 sensitivity SUMMARY TABLE: measured (a) substrate W-pattern density vs bias-free D2 EXPANDED N=71 baseline; (b) per-variable substrate regime fingerprint (90d return / ATR% / 52w prox / sector mix); (c) cross-variable compatibility profile.

**Headline finding**: V2 substrates are systematically ENRICHED for W-pattern productivity on a per-ticker basis (D_filt = 7.2x-70x baseline 0.138) but substrate SIZE is too small for defensible per-ruleset evaluation under the canonical filter (T<=15 in all 5 cases; T<5 in 3 of 5; baseline T=516). The "substrate thinness" framing in prior R2-A/R2-D findings docs was a function of small T, NOT low per-ticker W incidence. R2-A's prior rejecting Ruleset E verdict + R2-D's insufficient-sample finding reflect substrate-size + survival-quality limitations rather than W-pattern depletion.

---

## Sec 2 Implementation Summary

### Sec 2.1 NEW modules

5 NEW Python modules under `research/harness/`:

| Module set | Files | Purpose |
|---|---|---|
| `v2_tightness_range_factor/` | __init__ + cohort_csv + regenerate_cohort | NEW cohort extraction (vcp.tightness_range_factor sp=1.005; 67 raw flips / 15 unique tickers / 29 unique pairs) |
| `v2_proximity_max_pct/` | __init__ + cohort_csv + regenerate_cohort | NEW cohort extraction (vcp.proximity_max_pct sp=7.5; 5 raw flips / 3 unique tickers / 3 unique pairs) |
| `v2_orderliness_max_bar_ratio/` | __init__ + cohort_csv + regenerate_cohort | NEW cohort extraction (vcp.orderliness_max_bar_ratio sp=3.75 first-crossing LOCK; 1 raw flip; 1 ticker LASR) |
| `v2_selection_mechanic/` | __init__ + substrate_characterization + w_density_analysis + synthesis + run | Analytical orchestration (5 modules) |
| (REUSE) `r2a_tightness_days_required/` | (preserved verbatim per sibling-module LOCK) | R2-A cohort extraction (REUSE; byte-stability tested) |
| (REUSE) `r2d_adr_min_pct/` | (preserved verbatim per sibling-module LOCK) | R2-D cohort extraction (REUSE; byte-stability tested) |

### Sec 2.2 NEW artifacts

| Artifact | Path |
|---|---|
| 3 V2 cohort CSVs | `exports/research/cohorts/v2_{tightness_range_factor,proximity_max_pct,orderliness_max_bar_ratio}_sp*.csv` |
| 3 V2 cohort audit JSONs | `exports/research/cohorts/v2_*_sp*.flips_audit.json` |
| Smoke artifact directory | `exports/research/v2-selection-mechanic-analysis-20260527T084319Z/` (manifest + summary + per_variable_signals + substrate_characterization + w_density_detail + compatibility_synthesis; 6 files) |
| Study writeup | `research/studies/2026-05-26-v2-selection-mechanic-analysis.md` |
| Findings doc | `docs/v2-selection-mechanic-analysis-findings-2026-05-26.md` |
| Return report | `docs/v2-selection-mechanic-analysis-return-report.md` (this file) |

### Sec 2.3 ZERO production swing/ writes

The investigation is analytical-only. No production code modified. L2 LOCK preserved + REINFORCED via parametric source-grep tests across the NEW v2_selection_mechanic module set.

---

## Sec 3 Commit-Cadence Ledger

14 commits since branch base `55d0f48`:

| # | Commit | Slice | Tests added |
|---|---|---|---|
| 1 | `a201c82` | Slice 1 v2_tightness_range_factor | 34 |
| 2 | `e1eb901` | Slice 2 v2_proximity_max_pct | 29 |
| 3 | `474b396` | Slice 3 v2_orderliness_max_bar_ratio (sp=3.75 LOCK) | 29 |
| 4 | `eebf4bf` | Slice 4a foundation (BINDING_SIGNALS_TABLE + gotcha #34) | 9 |
| 5 | `ed020e6` | Slice 4b primitives (substrate_characterization + w_density_analysis) | 34 |
| 6 | `af2e9e6` | Slice 4c orchestration (synthesis + run.py + gotcha #33 banned-terms) | 23 |
| 7 | `47f0912` | Codex chain #1 R1 fix bundle (2 CRITICAL + 4 MAJOR closed) | +12 discriminating |
| 8 | `24e79ef` | Codex chain #1 R2 fix bundle (3 MAJOR + 1 MINOR closed) | +6 discriminating |
| 9 | `9097f08` | Codex chain #1 R3 fix bundle (3 MAJOR closed + 1 MINOR banked V2) | +4 discriminating |
| 10 | `e78fb77` | Codex chain #1 R4 fix bundle (2 MAJOR + 1 MINOR closed) | +6 discriminating |
| 11 | `836bfe4` | Slice 5 smoke artifact + dual-density framing | +3 discriminating |
| 12 | `a86fbc4` | Slice 6 study writeup + Brief Amendments 3+4 (3-metric framing + 3-axis profile tags) | 0 |
| 13 | `fcc5e37` | Codex chain #2 R1 fix bundle (3 MAJOR closed: banned-term substrings + arithmetic + survival range) | 0 |
| 14 | `9c6cea6` | Codex chain #2 R2 MINOR closed (hedging-tightening) | 0 |

Plus this Slice 8 commit (findings doc + return report).

Test scope: **196 fast tests green** across the V2-selection-mechanic suite + 4 sibling cohort modules. Pre-Codex baseline was 158; +38 R1-R5 + slice 5 discriminating tests added through Codex chain #1.

---

## Sec 4 Codex MCP Adversarial Review Chain

Per operator-paired LOCK at investigation greenlight 2026-05-26 PM: TWO Codex chains (chain #1 reviews implementation; chain #2 reviews study writeup methodology). **43rd cumulative C.C lesson #6 validation slot spans BOTH chains.**

### Chain #1 (code review; slices 1-5)

| Round | Critical | Major | Minor | Action | Commit |
|---|---|---|---|---|---|
| R1 | 2 | 4 | 0 | All 6 closed in-place | `47f0912` |
| R2 | 0 | 3 | 1 | All 4 closed; 3 R1-fix cascade regressions per gotcha #21 | `24e79ef` |
| R3 | 0 | 3 | 1 | 3 MAJOR closed; 1 MINOR deferred V2 (sibling-module LOCK preserved) | `9097f08` |
| R4 | 0 | 2 | 1 | All 3 closed | `e78fb77` |
| R5 | 0 | 0 | 0 | **CONVERGENCE: NO_NEW_CRITICAL_MAJOR** | (no commit) |

Cumulative chain #1: **2 CRITICAL + 12 MAJOR + 3 MINOR (17 findings); 16 closed in-place; 1 MINOR banked V2 candidate.**

### Chain #2 (study writeup methodology + numerical accuracy; slice 6)

| Round | Critical | Major | Minor | Action | Commit |
|---|---|---|---|---|---|
| R1 | 0 | 3 | 1 | All 4 closed (banned-term substrings + tightness_range_factor arithmetic + survival-range understatement + adr_min_pct cross-variable language) | `fcc5e37` |
| R2 | 0 | 0 | 1 | MINOR closed (hedging-tightening); **CONVERGENCE: NO_NEW_CRITICAL_MAJOR** | `9c6cea6` |

Cumulative chain #2: **0 CRITICAL + 3 MAJOR + 2 MINOR (5 findings); all 5 closed in-place.**

### Total chain ledger

**22 findings across both chains (2 CRITICAL + 15 MAJOR + 5 MINOR); 21 closed in-place; 1 MINOR banked V2 candidate.**

---

## Sec 5 Test Status

`python -m pytest tests/research/v2_selection_mechanic/ tests/research/v2_tightness_range_factor/ tests/research/v2_proximity_max_pct/ tests/research/v2_orderliness_max_bar_ratio/ -q` -> **196 passed in ~5s** (NEW test surface; ZERO failures).

Existing R2-A + R2-D byte-stability tests preserved (98 tests green; per sibling-module strategy LOCK).

Broader project fast-suite verification deferred to orchestrator post-merge per dispatch brief Sec 5.2.

---

## Sec 6 V1 Simplifications + V2 Candidates Banked

Per dispatch brief + cumulative discipline V2-banking precedent:

1. **D2 baseline canonical_survival_rate UNAVAILABLE in V1** (Option B fallback). Re-run D2 EXPANDED with results.csv emission enabled. Closes L4-style limitation.
2. **R2-A "~13%" narrative-anchor reconciliation** vs this investigation's 5.1% measurement (~2.5x discrepancy; likely extraction-parameter divergence). Closes L5-style limitation.
3. **Sector resolution V1 UNKNOWN** (no finviz CSV passed; all 5 V2 substrates show dominant_sector=UNKNOWN). Extend to candidates table query per dispatch brief Sec 1.5 multi-source fallback. Closes L6-style limitation.
4. **Substrate-size augmentation experiments.** Aggregate watch->aplus flips across multiple V2 binding variables to construct substrate-size-sufficient (T>=20) V2-style cohort for defensible per-ruleset evaluation.
5. **Common-parser refactor** for sibling cohort modules (R2-A + R2-D + 3 NEW V2 sibling modules). Sibling-module strategy LOCK preserved through this investigation per dispatch brief Sec 2.1.
6. **Immutable archive snapshot for V2-style readers** (per gotcha #26 family). Not directly affecting this analytical investigation; forward-binding for future investigations requiring byte-identical archive contents.
7. **Pre-Codex review Expansion #19 candidate**: substrate density metric disambiguation discipline. Codex chain #2 R1 surfaced 2 banned-term substring slips in the study writeup (R1.M#1) that escaped pre-Codex review despite gotcha #33 lock. Suggests an expansion of cumulative gotcha discipline to include "brief-vs-prior-arc numerical anchor cross-reference must include exact filter parameters." Banked for post-merge CLAUDE.md gotcha discipline expansion.
8. **Detection-runs detail under smoke artifact `detection_runs/` subdirectory**: NOT committed (gitignored; operator can re-run via `python -m research.harness.v2_selection_mechanic.run --execute`). The 5 per-substrate detection runs + their per-(variable, ticker, asof) verdict CSVs are reproducible via the canonical invocation.

---

## Sec 7 Cumulative Discipline Preservation

| Discipline | Status |
|---|---|
| ZERO Co-Authored-By trailer drift | Preserved across 14 commits (~570+ cumulative project-wide; this investigation contributes 14) |
| ZERO production swing/ writes | Preserved |
| ZERO new Schwab API calls (L2 LOCK) | Preserved + REINFORCED via parametric source-grep tests |
| ZERO yfinance imports at runtime (gotcha #28+29) | Preserved; OHLCV reads via `pd.read_parquet` directly + strict guards |
| Schema v21 unchanged (no migrations) | Preserved |
| ASCII discipline (gotcha #32) | Declared scope verified across all NEW Python + Markdown + CSV |
| Banned verdict terms (gotcha #33) | Locked at synthesis layer + Codex chain #2 R1 fix bundle closed 2 prior-arc-citation slips |
| Cross-table verification (gotcha #34 FIRST + SECOND canonical application) | BINDING_SIGNALS_TABLE + NON_WATCH_TRANSITION_GAP_TABLE programmatically verified |
| Sibling-module strategy LOCK | Preserved (3 NEW + REUSE R2-A + REUSE R2-D; no common-parser refactor) |
| feedback_verify_regression_test_arithmetic | Honored across NEW discriminating tests (90d return / ATR / D_filt arithmetic discriminators added) |
| feedback_pause_means_pause | Honored at investigation greenlight, dual-Codex-chain handoffs, and Slice 5 methodological-ambiguity triage |
| Pre-Codex review expansions #1-#18 | Applied per operator triage; #19 candidate banked V2 |
| 43rd cumulative C.C lesson #6 validation | Spans BOTH chains; CLEAN at convergence + cumulative gotcha discipline NOTABLE (1 NEW expansion candidate #19 banked) |

---

## Sec 8 Acceptance Criteria Checklist

Per dispatch brief Sec 5.1-5.5:

### Sec 8.1 Functional
- [x] 3 NEW cohort extraction module sets at `research/harness/v2_{tightness_range_factor,proximity_max_pct,orderliness_max_bar_ratio}/` (3 modules x 3 = 9 files)
- [x] 1 NEW analytical orchestration module set at `research/harness/v2_selection_mechanic/` (5 modules)
- [x] 3 NEW cohort CSVs at `exports/research/cohorts/v2_*_sp*.csv`
- [x] 3 NEW sibling audit JSONs at `exports/research/cohorts/v2_*_sp*.flips_audit.json`
- [x] 1 NEW analytical smoke artifact directory at `exports/research/v2-selection-mechanic-analysis-20260527T084319Z/` (6 files: manifest + summary + 3 CSVs + synthesis MD)
- [x] 1 NEW study writeup at `research/studies/2026-05-26-v2-selection-mechanic-analysis.md`
- [x] 1 NEW findings doc at `docs/v2-selection-mechanic-analysis-findings-2026-05-26.md`
- [x] 1 NEW return report at `docs/v2-selection-mechanic-analysis-return-report.md` (this file)
- [x] BINDING_SIGNALS_TABLE module constant LOCKED + cross-table verified per gotcha #34

### Sec 8.2 Test scope
- [x] 196 fast tests green across V2-selection-mechanic + 4 sibling cohort suites (exceeds brief's ~100-140 estimate via discriminating-test additions through Codex chain #1)
- [x] R2-A + R2-D existing tests still green (98 tests; byte-stability preserved)
- [x] pattern_cohort_evaluator + D2 + D1 byte-stability inherited (no modifications)
- [x] Broader project fast suite: deferred for orchestrator-side verification

### Sec 8.3 Discipline preservation (per Sec 7 above)
- [x] ZERO Co-Authored-By footer drift
- [x] ZERO production `swing/` writes
- [x] Schema v21 unchanged
- [x] L2 LOCK preserved + REINFORCED
- [x] ZERO new Schwab API calls
- [x] ASCII discipline complete
- [x] Sibling-module strategy LOCK preserved

### Sec 8.4 Analytical deliverables
- [x] 5-row per-variable signal table (filled with measured numbers; 3-axis profile tags)
- [x] Per-variable regime fingerprint table (median + IQR per metric + sector mix)
- [x] Bias-free baseline W-density measurement + delta computation
- [x] Compatibility narrative synthesis (per-variable; per Brief Amendment 4)
- [x] 4-way cross-arc carryover (D2 EXPANDED + R2-A + R2-D + this investigation)
- [x] V2 candidates banked (8 items in Sec 6 above)

### Sec 8.5 Cumulative discipline
- [x] CLAUDE.md gotcha #34 FIRST + SECOND canonical applications shipped (BINDING_SIGNALS_TABLE + NON_WATCH_TRANSITION_GAP_TABLE)
- [x] CLAUDE.md gotcha #33 third canonical application REINFORCED (NO banned verdict terms in synthesis output; Codex chain #2 R1 fix bundle closed 2 study-writeup substring slips)
- [x] CLAUDE.md gotchas #1-#34 fully BINDING through both Codex chains
- [x] 43rd cumulative C.C lesson #6 validation slot consumed (spans both Codex chains)
- [x] Expansion #19 candidate banked V2 (substrate density metric disambiguation)

---

## Sec 9 Handoff to Orchestrator

**Suggested merge commit message (orchestrator-side at merge):**

```
Merge applied-research-v2-selection-mechanic-investigation into main:
V2-selection-mechanic ANALYTICAL investigation SHIPPED -- 5 V2 binding
variables characterized via per-variable 3-axis profile tags (productivity
/ size / survival); D_filt = 7.2x-70x baseline (V2 substrates are
ENRICHED for W-pattern productivity on per-ticker basis; substrate
thinness framing in R2-A/R2-D was small-T not low-W-incidence); NEW
first-class study writeup at research/studies/2026-05-26-v2-selection-mechanic-analysis.md;
NEW findings doc + return report; Brief Amendments 1-4 banked
orchestrator-side; Codex MCP chain #1 (5 rounds; 2C + 12M + 3m;
converged R5 NO_NEW_CRITICAL_MAJOR) + chain #2 (2 rounds; 0C + 3M +
2m; converged R2 NO_NEW_CRITICAL_MAJOR); 43rd cumulative C.C lesson #6
validation NOTABLE (spans BOTH chains; 1 NEW expansion #19 candidate
banked = substrate density metric disambiguation); gotcha #34 FIRST +
SECOND canonical applications shipped; gotcha #33 third canonical
application REINFORCED + 2 study-writeup substring slips closed
in-place; 14 implementer commits ZERO Co-Authored-By trailer; ZERO
production swing/ writes; ZERO new Schwab API calls; L2 LOCK preserved
+ REINFORCED.
```

**Suggested CLAUDE.md status-line amendment** (orchestrator post-merge housekeeping):
- Update "Current state" line to reflect V2-selection-mechanic investigation SHIPPED at this merge SHA
- Bank Expansion #19 candidate (substrate density metric disambiguation) into the cumulative pre-Codex review checklist
- Update C.C lesson #6 validation counter: 42 (R2-D pre-investigation) -> 43 (V2-selection-mechanic SHIPPED; NOTABLE per Codex chain coverage)
- Bank Brief Amendments 1-4 as historical record (two-Codex-chain refinement; D2 baseline 88->516 correction; substrate density metric disambiguation; compatibility verdict structure clarification)

**Pending operator decision** (deferred to post-merge):
- L4-style D2 baseline results.csv re-emission for canonical_survival_rate baseline anchor: V2 candidate; not blocking
- L5-style R2-A "~13%" narrative-anchor reconciliation: V2 candidate; not blocking
- Substrate-size augmentation experiment scoping: V2 candidate; potentially next-arc after methodology validation here

---

*End of V2-selection-mechanic investigation return report. Primary artifact at `research/studies/2026-05-26-v2-selection-mechanic-analysis.md`. Findings doc at `docs/v2-selection-mechanic-analysis-findings-2026-05-26.md`. ZERO production swing/ writes; ZERO new Schwab API calls; ZERO Co-Authored-By trailer drift; investigation arc COMPLETE end-to-end with two-Codex-chain convergence.*
