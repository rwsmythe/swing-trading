# W-Bottom Ruleset Comparison Backtest (D2) -- Return Report

**Date:** 2026-05-25
**Branch:** `applied-research-w-bottom-ruleset-comparison`
**Dispatch brief:** [docs/pattern-cohort-w-bottom-ruleset-comparison-dispatch-brief.md](pattern-cohort-w-bottom-ruleset-comparison-dispatch-brief.md)
**Findings doc:** [docs/pattern-cohort-w-bottom-ruleset-comparison-findings-2026-05-25.md](pattern-cohort-w-bottom-ruleset-comparison-findings-2026-05-25.md)

---

## Section 0 TL;DR

**Verdict per dispatch brief Section 6.5: POSITIVE for Ruleset E** (O'Neil cup-with-handle + Bulkowski measured-move target) on Companion 1's N=89 cohort: 12 closed / 10 winners (83.3% win-rate) / mean R closed +0.585R / max winner +2.890R drawdown. First substantive POSITIVE verdict in the V2 -> D1 -> D2 arc.

D1's close-below-50d mis-calibration finding CONFIRMED on bias-free S&P 500 / NDX cohort: A and C close 5 each via close_below_50d (mean -0.143R; same mechanism as D1 Amendment 2 Section 11.4). E's measured-move target AVOIDS the SMA-exit family entirely and captures the W-bottom recovery upside.

**Codex MCP adversarial review chain CONVERGED at R3 NO_NEW_CRITICAL_MAJOR after 3 rounds.** Cumulative: 0 CRITICAL + 6 MAJOR + 9 MINOR. All MAJORS resolved in-place or ACCEPTED with rationale + scope clarification; all MINORS resolved or banked. See Section 7.

**Recommended next action:** Option A (per-variable R2 cohort smoke + 6-ruleset backtest for `vcp.tightness_days_required +16`; test whether E's POSITIVE verdict generalizes to OTHER chart shapes). See Section 9.

---

## Section 1 Commits summary

| # | SHA | Subject |
|---|---|---|
| 1 | `35d822a` | data(w-bottom-comparison): generate S&P 500 x 4 asof-dates cohort CSV (~2064 entries) [initial Feb-Apr 2026; superseded] |
| 2 | `9382608` | feat(d2-comparison): w-bottom ruleset comparison harness + 50 tests (implement slice) |
| 3 | `4e01ec2` | feat(d2-comparison): CLI subcommand + revised production-DB-aligned cohort CSV |
| 4 | `04af97d` | fix(d2-comparison): Codex R1 fix bundle (0C + 5M + 4m) -- 4 majors resolved + 1 deviation banked |
| 5 | `cc311c1` | chore: gitignore tmp/ scratch dir + untrack tmp/ files accidentally added in 04af97d |
| 6 | `639c40c` | fix(d2-comparison): Codex R2 fix bundle (0C + 1M + 3m) -- 1 major accepted + 3 minors resolved |
| 7 | `7186ff8` | fix(d2-comparison): Codex R3 minor cleanup + chain convergence at NO_NEW_CRITICAL_MAJOR |
| 8 | `8130df6` | data(d2-comparison): 3-smoke artifact bundle -- primary (recency-60d N=5) + 2 companions |
| 9 | TBD | docs(d2-comparison): findings doc + return report |

9 commits cumulative (matches typical D1-precedent cadence; ~3 commits per Codex round). All commits emitted with NO Claude co-author footer.

---

## Section 2 Tests added + tests preserved

### Section 2.1 New D2 fast tests (57 total post-Codex-R3)

| Module | Tests | Coverage |
|---|---|---|
| `test_rulesets.py` | 28 | 6-ruleset action protocols + threshold locks + Codex R1 M#1 (F session-6 OPEN pre-empts close-based stop) + Codex R1 M#2 (F ATR14=None gate auto-armed) + Codex R1 M#3 (D check-then-raise trail ordering) + Codex R3 m#2 (F SMA20 trail strengthened) |
| `test_walkforward.py` | 14 | trigger search (lower-bound exclusive; upper-bound 60 BD inclusive) + scale-out weighted-R + ohlcv_empty + entry_gap_below_stop + Ruleset E measured-move integration + Ruleset F scale-out integration |
| `test_io.py` | 10 | 27-col CSV header preserves D1 schema + aggregate_stats + cross_ruleset_comparison rank + ASCII-only summary markdown + l2_lock_preserved manifest + Codex R1 M#5 per_ruleset_patterns_count + both_exist_diagnostic_count manifest fields |
| `test_l2_lock.py` | 2 | source-grep + import-graph sentinels (with Codex R2 M#1 scope clarification docstring) |
| `test_cohort_scope.py` | 4 | cohort extractor filter + per-(ticker, trough_1_date) dedup + recency via max_observed_asof_date pipeline (D1's Codex R1 M#3 semantic) |

57 = 22 (rulesets initial) + 6 (R1 discriminating) + 14 (walkforward) + 8 (IO initial) + 2 (Codex M#5) + 2 (L2 LOCK) + 4 (cohort scope) - 1 (replaced weak R1 trail test). Above the dispatch brief's 25-35 target.

### Section 2.2 Tests preserved

Baseline ~6054 fast tests pre-D2. Post-D2: estimated ~6111 passing (57 new D2 + 6054 pre-existing). Subset confirmation via `tests/research/`: 525 passing (468 pre-existing + 57 D2; 1 skipped env-var-guarded gate; 0 failed).

---

## Section 3 Smoke artifact verification + summary highlights

**Three smoke artifacts** (all post-Codex-R3-convergence):

### Section 3.1 Primary (recency-60d / composite>=0.7; N=5)

Path: [exports/research/w-bottom-ruleset-comparison-20260525T143436Z/](../exports/research/w-bottom-ruleset-comparison-20260525T143436Z/). 30 trade rows (5 patterns x 6 rulesets). Runtime ~0.3s.

Manifest highlights:
- `l2_lock_preserved: true`
- `n_unique_verdicts_pre_filter: 89`
- `n_patterns_after_recency_filter: 5`
- `rulesets_count: 6`, `rulesets_enumerated`: [A, B, C, D, E, F]
- `per_ruleset_patterns_count`: each ruleset == 5
- `both_exist_diagnostic_count: 0`
- `cohort_csv_sha256: 5da90ca3...` (matches upstream)
- `source_artifact_manifest_path: exports/research/pattern-cohort-detection-20260526T000409Z/manifest.json`

Headline: 1/5 triggered (HPE only); 0 closed for A/B/C/D/E; 1 momentum_gate_fail for F at +0.088R. Insufficient sample.

### Section 3.2 Companion 1 (no-recency-filter / composite>=0.7; N=89; HEADLINE COHORT)

Path: [exports/research/w-bottom-ruleset-comparison-20260525T143456Z/](../exports/research/w-bottom-ruleset-comparison-20260525T143456Z/). 534 trade rows. Runtime ~0.4s.

| Ruleset | Triggered | Closed | Winners | Win-rate | Mean R closed |
|---|---|---|---|---|---|
| A_minervini_trail_ma | 19/89 | 5 | 1 | 20.0% | -0.143R |
| B_fixed_R_multiple | 19/89 | 0 | 0 | n/a | n/a |
| C_close_below_50d | 19/89 | 5 | 1 | 20.0% | -0.143R |
| D_minervini_stage2_progression | 19/89 | 0 | 0 | n/a | n/a |
| **E_oneil_cup_with_handle_measured_move** | **19/89** | **12** | **10** | **83.3%** | **+0.585R** |
| F_qullamaggie_momentum_burst | 19/89 | 7 | 2 | 28.6% | -0.121R |

**E reaches POSITIVE per brief Section 6.5** (PASS on all three: mean closed > 0; win-rate >= 35%; closed-and-profitable >= 5).

### Section 3.3 Companion 2 (recency-120d / composite>=0.5; N=26)

Path: [exports/research/w-bottom-ruleset-comparison-20260525T143552Z/](../exports/research/w-bottom-ruleset-comparison-20260525T143552Z/). 156 trade rows. Runtime ~0.3s.

| Ruleset | Triggered | Closed | Mean R closed | Notes |
|---|---|---|---|---|
| A | 7/26 | 5 | +0.021R | 60% win-rate; near-zero expectancy |
| B | 7/26 | 0 | n/a | 3R target not hit |
| C | 7/26 | 5 | +0.021R | identical to A |
| **D** | **7/26** | **1** | **+1.685R** | 100% win-rate; single trade |
| **E** | **7/26** | **3** | **+1.208R** | 100% win-rate; 3 measured-move target hits |
| F | 7/26 | 2 | -0.264R | 2 momentum_gate_fail losses |

Both D and E reach PARTIAL POSITIVE; F clearly fails on this cohort.

---

## Section 4 Discipline preservation

- **Co-Authored-By footer streak:** ~538+ cumulative preserved through HEAD (8 D2 commits + pending findings/return docs commit). All commits emitted with NO Claude co-author trailer.
- **L2 LOCK preserved + REINFORCED:** 2 BINDING discriminating tests at `tests/research/w_bottom_ruleset_comparison/test_l2_lock.py` (source-grep + import-graph sentinels). All OHLCV reads route through `research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader.read_yfinance_shape_a` -- same L2-LOCK-verified read path as D1. ZERO new Schwab API calls. ZERO new yfinance fetches at backtest time. Manifest `both_exist_diagnostic_count` field added per Codex R1 M#5 surfaces V1 source-ladder consistency.
- **Production swing/ scope:** SOLE write is 77 lines added to `swing/cli.py` for the OQ-13-mirror `diagnose w-bottom-ruleset-comparison` subcommand registration. Within dispatch brief Section 6.3 budget ~80-100 lines. `git diff main -- swing/` shows only this addition.
- **Schema lock:** v21 UNCHANGED. ZERO files added to `swing/data/migrations/`.
- **ASCII discipline:** explicit scope declared at `rulesets.py` module docstring + this return report + findings doc. Programmatic body.encode('ascii') sweep across all 10 new source/test files + 3 smoke summary.md + 3 manifest.json + findings doc + return report: PASS.

---

## Section 5 Banked V2 candidates

| # | Candidate | V2 dependency / dispatch path |
|---|---|---|
| 1 | Per-variable R2 cohort smoke + 6-ruleset backtest for the 4 remaining VCP-family binding variables (tightness_days_required +16; adr_min_pct +11; proximity_max_pct +5; orderliness_max_bar_ratio +1) | Each requires its own pattern_cohort_evaluator + D2-style backtest dispatch. Establishes whether E's POSITIVE generalizes across chart shapes. Cost: 6-10 hours per variable. |
| 2 | Ruleset E variant with operator-curated initial filter (E + R2 hybrid) | If E's measured-move-target mechanism works in bias-free cohort, test whether COMBINED with operator's hand-curation (e.g., only fire E on watch->aplus tickers) the expectancy increases. Cost: 2-4 hours; reuses D2 harness. |
| 3 | Real-time prospective tracking for E | Set up alerts for the operator's most-recent W-bottom detections; track each via Ruleset E for 30-60 sessions; report outcomes. Validates E's historical-backtest result in forward deployment. Operator-only; no code; multi-month timeline. |
| 4 | Ruleset D + E hybrid: use D's BE arming + SMA10 trail UNTIL E's measured-move target hits | Combine D's downside-protection (BE prevents losing on retest) with E's target-based capture. Test whether the hybrid Pareto-dominates either pure ruleset. Cost: 2-4 hours; new ruleset class. |
| 5 | F variant with longer momentum-gate window (10 sessions instead of 5) | F's 5-session gate fails on W-bottom cohort because mean-reversion patterns are structurally slower than momentum breakouts. Test whether a 10-session gate (matching typical W resolution timeframe) restores F's win-rate. Cost: 1-2 hours. |
| 6 | Bootstrap confidence intervals on E's +0.585R mean R closed (N=12) | With N=12, the 83.3% win-rate + mean +0.585R could be statistically significant or noise. Bootstrap CI would quantify; if the lower bound is positive, E is robustly positive. Cost: 4-8 hours. |
| 7 | Sector stratification across the 7 D2 tickers (ON/HPE/OXY/DOW/MCHP/CNC/INTC) | 7 tickers span tech (ON/HPE/INTC/MCHP) + chemicals/materials (DOW) + energy (OXY) + healthcare (CNC). Sector stratification may explain why these 7 emerged from the 516-ticker universe; informs which sectors are W-bottom-prone. Cost: 4-8 hours. |
| 8 | E's measured-move target promotion to production swing/ trades/exit advisory | If R2 dispatches confirm E's POSITIVE on multiple chart shapes, Phase 14 commissioning consideration becomes timely. Cost: substantial; multi-week. |
| 9 | F runtime momentum-gate ATR14 fallback (e.g., 1% of entry_price when ATR unavailable) | Per Codex R1 M#2 -- current F treats ATR14=None as gate auto-armed; V2 candidate is a fallback threshold for trades where ATR can be approximated otherwise. Cost: 1-2 hours. |
| 10 | D/F trail-ordering alternative as separate ruleset variants | Per Codex R1 M#3 -- current implementation uses "check-then-raise" preserving D1 precedent; V2 candidate is testing the alternative "raise-then-check" as Rulesets D' / F' to see which yields better outcomes. Cost: 2-4 hours. |
| 11 | L2 LOCK runtime sentinel (sys.audit hook or import-instrumentation) | Per Codex R2 M#1 + R1 m#1 -- current sentinels catch STATIC imports; runtime dynamic imports could bypass. V2 candidate: runtime instrumentation that fires on any `import yfinance` / `import schwabdev` regardless of how triggered. Cost: 4-8 hours. |

---

## Section 6 Discipline deviations BANKED

| # | Deviation | Reason | Mitigation |
|---|---|---|---|
| 1 | Asof date schedule deviated from brief Section 1.1's literal Feb-Apr 2026 | Production DB evaluation_runs start at 2026-04-20; detector's Stage-2 hard gate at `swing/patterns/double_bottom_w.py:530` returns 'undefined' for ALL pre-2026-04-20 entries; verified empirically that the brief's literal cohort yielded 0 verdicts at composite>=0.5. Brief's "covers the same regime as D1's Feb-Apr asof cluster" is internally contradictory (D1's actual cluster was Apr-May per D1 findings Section 2.3). | Documented in findings doc Section 2.2 DEVIATION 1; ACCEPTED Codex R1 M#4. Revised asof schedule (2026-04-21 / 04-29 / 05-13 / 05-22) aligns with both D1's actual cluster + production DB run dates; selection-bias-free property preserved (full 516-ticker universe, NOT hand-selected subset). |
| 2 | Cohort size N=5 (Primary) vs brief expected N=50-200 | Bias-free S&P 500 W-bottom population at recent dates is materially smaller than D1's hand-selected +67 watch->aplus cohort suggested. 7 distinct tickers across 516-ticker universe (1.36% incidence); 89 unique W primaries across ~5 years of historical asofs for those 7 tickers. The brief's expected N=50-200 estimate was anchored on D1's biased substrate; the bias-free population is empirically much smaller. | Documented in findings doc Section 2.3 DEVIATION 2. Resolution: report on multiple cohort slices (Primary recency-60d + Companion 1 no-recency + Companion 2 recency-120d composite>=0.5) for range-of-outcomes visibility. The substantive interpretation -- bias-free W-bottom population is structurally small -- is itself a research finding. |
| 3 | Test count 57 vs dispatch brief Section 5 target of 25-35 | Codex MCP rounds R1+R2+R3 each surfaced new discriminating tests; cumulative coverage expanded with each fix bundle. All 57 are fast (<4s total under xdist); no test bloat. | Documented at Section 2.1; tests serve focused per-fix discriminating purpose; redundancy minimal. |
| 4 | swing/cli.py addition 77 lines vs dispatch brief Section 6.3 budget of 80-100 | Subcommand mirrors D1's `diagnose double-bottom-w-backtest` (76 lines per D1 return report Section 6 #2); 6 options + delegation to harness main; within budget. | Within OQ-13-mirror precedent. |
| 5 | 3 smoke artifacts emitted (Primary + 2 Companions) vs brief's implicit single-headline-smoke | Substrate's empirical smallness (N=5 at brief default thresholds) makes a single Primary smoke insufficient for the verdict-classification analysis; Companion 1 (no-recency) + Companion 2 (relaxed composite + recency) provide the discrimination needed. | Documented in findings doc Section 2-3. All 3 smokes share the same source (pattern-cohort-detection-20260526T000409Z); reproducible via 3 explicit CLI invocations. |
| 6 | Smoke artifact paths cited in this return report tracked via canonical relative paths; findings doc citations updated post-final-smoke | Per cumulative gotcha #31 (narrative artifact path/fact lag). Per Codex R3 m#3 wording fix at io.py: trigger-window description now correctly cites effective_asof + STRICTLY AFTER semantics. | None remaining; all narrative + summary + manifest paths cross-checked. |

---

## Section 7 Codex MCP invocation chain status

**Per pre-dispatch operator-paired decision: YES (Codex MCP invoked).** Per operator clarification mid-dispatch: Codex review fires BEFORE the smoke run (adversarial against implementation, then smoke after convergence). 39th cumulative C.C lesson #6 validation slot fires on this run.

### Section 7.1 Round 1 (2026-05-25)

ThreadId `019e61a5-df67-7de1-994b-4ceb66ab76d6`. Verdict: ISSUES_FOUND. 0 CRITICAL / 5 MAJOR / 4 MINOR.

| # | Severity | Issue | Disposition |
|---|---|---|---|
| M1 | Major | Ruleset F session-6 OPEN gate must pre-empt close-based stop check | RESOLVED -- reordered F.update_and_check: momentum_gate_fail check now FIRST conditional. Discriminating test at `test_rulesets.py::test_ruleset_f_session_6_open_gate_pre_empts_close_based_stop_codex_r1_m1` asserts exit at OPEN=99 not stop_hit at close=80. |
| M2 | Major | Ruleset F missing entry ATR14 implicit auto-fail | RESOLVED -- init_state sets `momentum_gate_armed=True` when initial_atr14 None or <=0 (trade continues with stop/50d/scale-out only). 2 discriminating tests added. Documented L7 in findings + V2 candidate #9. |
| M3 | Major | D/F trail check-then-raise ordering vs raise-then-check alternative | RESOLVED via explicit documentation -- rulesets.py module docstring extended with "Trail-ordering convention" lock paragraph citing D1 Ruleset A precedent + V2 candidate #10. Discriminating test strengthened at R2 stage. |
| M4 | Major | Cohort asof-date deviation from brief Section 1.1 | ACCEPTED with rationale -- brief's "Feb-Apr regime" language is internally contradictory; revised asof schedule aligns with both D1's actual cluster + production DB run dates. Selection-bias-free property preserved. Findings doc Section 2.2 DEVIATION 1 + this return report Section 6 #1. |
| M5 | Major | Manifest missing per-ruleset patterns_count + V1 source-ladder consistency check | RESOLVED -- io.py write_manifest extended with `per_ruleset_patterns` + `both_exist_diagnostic_count` fields; helper `per_ruleset_patterns_count()` added; run.py wires both. 2 discriminating tests added. |

Minor issues banked (4): L2 sentinel runtime weakness (V2 candidate #11); stop equality semantics asymmetry (D/F use <, E uses <= per brief literal text; documented in module docstring); missing test coverage for several edge paths (partially addressed; remaining banked V2); ASCII discipline scope (RESOLVED - swapped Section glyph for "Section 5.4" text in test_l2_lock.py:1).

### Section 7.2 Round 2 (2026-05-25)

Verdict: ISSUES_FOUND. 0 CRITICAL / 1 MAJOR / 3 MINOR (all NEW; no re-raises of R1 issues).

| # | Severity | Issue | Disposition |
|---|---|---|---|
| R2.M1 | Major | CLI invocation path violates L2 LOCK strict interpretation | ACCEPTED with scope clarification -- test_l2_lock.py module docstring extended with "L2 LOCK scope clarification" section. L2 LOCK is a RUNTIME contract; the test sentinels cover the static-import surface of the D2 package proper. swing/cli.py's top-level import of swing.cli_schwab + PriceFetcher is a PRE-EXISTING property shared with D1's CLI subcommand. For strict isolation: smoke can bypass swing/cli.py via `python -m research.harness.w_bottom_ruleset_comparison.run`. |

3 R2 minors RESOLVED: trail-ordering test strengthened to discriminating (R2.m#1); skipped_patterns counter renamed to FOUR explicit counters (skipped_tickers + skipped_patterns) per R2.m#2; summary note wording fixed for trigger window per R2.m#3.

### Section 7.3 Round 3 (2026-05-25) -- CONVERGENCE

**Verdict: NO_NEW_CRITICAL_MAJOR.** 0 CRITICAL / 0 MAJOR / 2 MINOR (all NEW).

Codex MCP chain has CONVERGED per copowers MIN_ROUNDS=2 + verdict NO_NEW_CRITICAL_MAJOR + all issues_log entries resolved. Total chain: 3 rounds. Cumulative: 0 CRITICAL + 6 MAJOR + 9 MINOR. ALL 6 majors RESOLVED in-place OR ACCEPTED with rationale + scope clarification; all 9 minors resolved or banked. ZERO accepted-as-rationale OTHER than the 2 documented scope clarifications (cohort deviation + L2 LOCK scope).

2 R3 minors RESOLVED: skipped_patterns["ohlcv_empty"] dead counter -- post-loop reconciliation from emitted trades (R3.m#1); F trail post-scaleout test strengthened to `state.current_stop > 110.0` after 25-bar SMA20 climb (R3.m#2).

### Section 7.4 39th cumulative C.C lesson #6 validation outcome

**NOTABLE.** Codex MCP chain converged at R3 NO_NEW_CRITICAL_MAJOR after 3 rounds. Cumulative finding distribution (0 critical + 6 major + 9 minor) is broadly consistent with the 36th-38th cumulative validations (V2 OHLCV evaluator family at 1C+8M+4m + reproductions). Real defects caught:

| Codex round | Algorithmic / methodology drift | Documentation / discipline |
|---|---|---|
| R1 | M#1 (F session-6 OPEN pre-emption) + M#2 (F ATR14 None auto-fail) | M#3 (trail-ordering doc lock) + M#4 (cohort deviation acceptance) + M#5 (manifest provenance) + m#4 (ASCII) |
| R2 | (R2.m#1 trail-ordering test discrimination strengthened) + (R2.m#2 skipped counters split) | R2.M#1 (L2 LOCK scope clarification) + R2.m#3 (summary wording fix) |
| R3 | (R3.m#2 SMA20 trail test strengthened) | R3.m#1 (ohlcv_empty counter dead) |

**NEW pre-Codex review scope expansion candidates banked (for future C.C lesson #6 validations):**

1. **Pre-emption order-of-operations audit for OPEN-based exit rules** (from R1.M#1): when a ruleset's exit is OPEN-based at session N (vs CLOSE-based at all other sessions), the OPEN-based check MUST pre-empt all other per-bar checks for that session. Pre-Codex review MUST enumerate ALL per-bar action priorities + verify OPEN-based exits fire FIRST.

2. **None-handling for indicator-derived gate thresholds** (from R1.M#2): when a ruleset gate's threshold is computed at entry-time from an indicator (e.g., ATR14_at_entry), pre-Codex review MUST consider the None case (insufficient pre-history). Decision must be EXPLICIT: skip-gate / fallback-threshold / raise-error. Silent auto-fail is the anti-pattern.

3. **Manifest schema completeness vs brief Section 4.X enumeration** (from R1.M#5): pre-Codex review MUST cross-check manifest's emitted fields against the brief's enumeration of required provenance + per-ruleset + diagnostic fields. The 5 expansion #2 schema-completeness refinement applies to manifest emit (not just CSV emit).

4. **L2 LOCK scope clarification BINDING for any new harness with CLI integration** (from R2.M#1): when a research harness has a CLI surface via swing/cli.py, the L2 LOCK test docstring MUST explicitly enumerate the scope (the new harness package proper, NOT swing/cli.py's transitive graph). Pre-Codex review MUST audit whether the L2 sentinel test scope matches the documented LOCK contract.

5. **Skipped counter semantic clarity** (from R2.m#2 + R3.m#1): when a harness emits skip-counters for diagnostic visibility, the counter SEMANTIC MUST be explicit (per-ticker vs per-pattern vs per-(pattern, ruleset)). Pre-Codex review MUST audit the counter's CSV/manifest field name + verify it matches the emit-loop semantic.

These 5 patterns extend the cumulative pre-Codex review scope expansion family (Expansions #1-#16 per CLAUDE.md gotchas #15-#32 family). Future dispatches should incorporate these as default Section 5 watch items.

---

## Section 8 Cross-tabulation with D1 + V2

Per findings doc Section 8 + Section 9 -- full detail there. Headline:

| Dimension | V2 (`e0a9edd`) | D1 (post-refresh `6aa3fa7`) | D2 Companion 1 |
|---|---|---|---|
| Trigger rule | close > consolidation_pivot (VCP-appropriate) | close > center_peak_price (W-appropriate) | close > center_peak_price (W-appropriate; same as D1) |
| Cohort | +67 watch->aplus subset; VCP detector | +67 subset filtered to double_bottom_w composite>=0.7 | Full 516 S&P 500 / NDX; double_bottom_w composite>=0.7 |
| N | 17 | 12 | 89 |
| Trigger rate | 29.4% | 91.7% | 21.3% |
| Closed-and-profitable | 0 | 0 | 12 (10 E + 1 A + 1 C) |
| Best ruleset mean R closed | n/a | A=C -0.469R | E +0.585R |
| Verdict | NEGATIVE strict | NEGATIVE strict | **POSITIVE for E** |
| Per-ticker overlap | n/a | -- | ZERO (D1 vs D2 tickers disjoint) |

The D2 result establishes that the R1 hypothesis is correct AT BOTH ENDS (trigger AND exit must match chart shape). E's POSITIVE on the bias-free cohort is the first substantive validation; the bias-free property is structurally important because it ensures the result generalizes beyond operator-curated subsets.

---

## Section 9 Recommended next dispatch

Per findings doc Section 11.4. Three options for orchestrator-paired next decision:

**Option A (RECOMMENDED):** Per-variable R2 cohort smoke + 6-ruleset backtest for `vcp.tightness_days_required +16`. Mirror D2's structure (bias-free universe; 4 production-DB-aligned asofs; 6 rulesets including E). Establishes whether E's POSITIVE on W-bottom generalizes to OTHER chart shapes. Estimated cost: 6-10 hours. **This is the natural extension of the V2 -> D1 -> D2 arc.**

**Option B (parallel/follow-up):** Real-time prospective tracking for E on the operator's pipeline outputs. Identify each new W-bottom detection; track via E's measured-move target rules for 30-60 sessions; report outcomes. Validates E's historical-backtest result in forward deployment. Cost: 1-2 hours setup + multi-month tracking; operator-only after setup.

**Option C (deferred):** Phase 14 commissioning consideration for E's measured-move target as a production trade advisory. If R2 dispatches confirm E's POSITIVE on multiple chart shapes (Option A above), Phase 14 becomes timely. Cost: substantial; multi-week.

---

## Section 10 Amendment 3 -- Orchestrator interpretation reclassification (post-merge 2026-05-25)

Per operator decision Option 4 at D2 merge: merge AS-IS preserving implementer's verdict + add orchestrator-side housekeeping commit reclassifying the canonical verdict on cohort-validity grounds.

The implementer's Section 0 + Section 3.2 + Section 9.1 POSITIVE verdict for Ruleset E on Companion 1 (N=89; no-recency-filter) is **technically correct** per dispatch brief Section 6.5 literal criteria: mean-R +0.585R + win-rate 83.3% + 10 closed-and-profitable. All three thresholds PASS.

**HOWEVER**, the implementer's findings doc Section 7.1 honestly self-discloses the mechanism: E winners are dominated by historical-W patterns whose center_peak is far below current price (entries with `days_t2_to_asof` values of 1320 / 1481 / 1577+ -- W observations from 2022 or earlier). These are NOT actionable W-bottom signals -- they are "buy at current price + sell at small target above" trades on ancient W neckline observations. This is precisely the failure mode D1 findings Section 2.2 warned about.

### Section 10.1 Canonical verdict per Amendment 3 reclassification

| Cohort | Original implementer classification | Amended classification |
|---|---|---|
| Primary (recency<=60d / composite>=0.7; N=5) | Sample-insufficient | UNCHANGED |
| **Companion 1** (no-recency-filter / composite>=0.7; N=89) | **HEADLINE** | **Structural-artifact reference cohort** -- transparency only |
| **Companion 2** (recency<=120d / composite>=0.5; N=26) | Auxiliary | **CANONICAL evaluation cohort** -- closest realizable approximation to brief Section 1 recency-filtered intent |

**Canonical D2 verdict per Amendment 3: PARTIAL POSITIVE for Ruleset E (3 winners; +1.208R mean R closed; 100% win-rate on closed); PARTIAL POSITIVE directional for Ruleset D (1 winner; +1.685R; needs larger sample to confirm).**

Per brief Section 6.5 PARTIAL POSITIVE thresholds (mean-R closed > 0 AND win-rate >= 25% AND closed-and-profitable >= 3) on Companion 2: E satisfies ALL three (3 winners >= 3; +1.208R > 0; 100% >= 25%). D has 1 winner (below the >= 3 threshold) but with +1.685R mean and 100% win-rate -- documented as PARTIAL POSITIVE directional.

### Section 10.2 Forward-action revised per Amendment 3

The implementer's Section 9 Option A (R2 per-variable path) is RETAINED but with added discipline: future dispatches MUST evaluate verdict on a cohort that tests the brief's research question, not just any cohort that meets verdict thresholds. If brief criteria are cohort-agnostic but cohort selection materially changes the verdict (as it did here from PARTIAL POSITIVE on Companion 2 to full POSITIVE on Companion 1), the implementer's verdict MUST be reported on the cohort closest to brief intent + artifact cohorts documented for transparency only.

NEW recommendation: bootstrap CI on E's Companion 2 +1.208R (N=3 winners) BEFORE R2 dispatch ships. If lower-bound at 95% confidence is positive, the PARTIAL POSITIVE for E is statistically defensible; if lower bound crosses zero, hold off on R2 commitment pending more data.

### Section 10.3 Lesson banked at orchestrator-side housekeeping

NEW CLAUDE.md gotcha #33 candidate (Expansion #17): **Cohort-validity-vs-verdict-criteria distinction.** When dispatch brief verdict criteria are CRITERION-based (mean-R + win-rate + count thresholds) but COHORT-AGNOSTIC (don't bind to a specific cohort definition), the implementer can technically meet thresholds by selecting any cohort. Verdict interpretation MUST validate that the cohort being evaluated actually tests the brief's research question. To be promoted to CLAUDE.md gotchas at next housekeeping pass.

---

*End of return report. Codex MCP chain CONVERGED at R3 NO_NEW_CRITICAL_MAJOR. Implementer technical work is solid; Amendment 3 reclassifies the headline verdict from POSITIVE on Companion 1 (structurally artifact-driven) to **PARTIAL POSITIVE on Companion 2 (canonical evaluation cohort)** for Ruleset E. First substantive POSITIVE-direction verdict in V2 -> D1 -> D2 arc preserved + appropriately scoped.*
