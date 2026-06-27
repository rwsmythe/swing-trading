# R2-D Backtest Findings: V2 OHLCV `vcp.adr_min_pct +11` Cohort 6-Ruleset Comparison

**Generated:** 2026-05-26
**Branch:** `applied-research-r2d-adr-min-pct-cohort-backtest`
**Dispatch brief:** [`docs/r2d-adr-min-pct-cohort-backtest-dispatch-brief.md`](r2d-adr-min-pct-cohort-backtest-dispatch-brief.md) (with Amendment 1)
**Return report:** [`docs/r2d-adr-min-pct-cohort-backtest-return-report.md`](r2d-adr-min-pct-cohort-backtest-return-report.md)
**Smoke artifact:** [`exports/research/w-bottom-ruleset-comparison-20260526T062529Z/`](../exports/research/w-bottom-ruleset-comparison-20260526T062529Z/)

---

## 1 Headline verdict: INSUFFICIENT SAMPLE (DIRECTIONAL POSITIVE color)

Per dispatch brief Amendment 1 section A1.2 + cumulative CLAUDE.md gotcha #33 BINDING (third canonical application of cohort-validity-vs-verdict-criteria discipline):

**Headline:** **INSUFFICIENT SAMPLE.** The R2-D canonical evaluation cohort yields **N=4 W primary verdicts, ALL from a single ticker (STNG)**. This substrate is well below the brief's expected N=50-200 range and is statistically indistinguishable from a single-ticker case study. The cross-cohort systemic-vs-cohort-specific research question (was R2-A's NEGATIVE unique to `vcp.tightness_days_required` OR systemic across V2 binding variables?) **CANNOT be answered with this substrate**.

**Color:** DIRECTIONAL POSITIVE on the per-ruleset closed trades that fired:
- E_oneil_cup_with_handle_measured_move: 1 of 1 closed-and-profitable at +0.800R (3 still open at data tail)
- F_qullamaggie_momentum_burst: 3 of 3 closed-and-profitable at +0.122R mean, 100% win-rate (1 still open)

**Cross-cohort discrimination test status:** **DEFERRED** to a future R2-* dispatch against a thicker V2 binding-variable substrate (e.g., `vcp.proximity_max_pct +5` or `vcp.orderliness_max_bar_ratio +1` per dispatch brief section 11.2 ordering).

**Why F's PARTIAL POSITIVE thresholds being met technically does NOT change the headline:**
Per dispatch brief Amendment 1 section A1.2 LOCK + gotcha #33 cohort-validity discipline (codified post D2 Amendment 3 + R2-A second application; THIRD canonical application here): the brief's PARTIAL POSITIVE thresholds (>=3 closed-and-profitable + mean-R > 0 + win-rate >= 25%) are CRITERION-based but COHORT-AGNOSTIC. With N=4 STNG-only patterns, any per-ruleset PARTIAL POSITIVE statistic is structurally a single-ticker case study, NOT a defensible "vcp.adr_min_pct +11 cohort produces PARTIAL POSITIVE for Ruleset F across V2-selected ticker substrate" claim. The DIRECTIONAL POSITIVE label preserves the empirical signal as informational color while honoring gotcha #33's "headline-verdict-must-match-research-question-fit" rule.

---

## 2 Cross-cohort 4-way comparison (MANDATED per brief section 7.3)

| Cohort | Definition | Size N | E closed | E closed-and-profitable | E mean R | E lower CI | E verdict |
|---|---|---|---|---|---|---|---|
| D1 post-refresh (`131423Z`) | Hand-curated +67 watch->aplus from V2 OHLCV `vcp.tightness_range_factor=1.005`; recency<=60d | 12 | n/a (E not tested at D1) | n/a | n/a | n/a | NEGATIVE-strict via DK + TROX close_below_50d |
| D2 Companion 2 canonical | Bias-free S&P 500; composite>=0.5 + recency<=120d | 26 | 6 | 3 | +1.208R | +0.464R | PARTIAL POSITIVE (degenerate) |
| D2 EXPANDED Amendment 5 | Bias-free S&P 500; composite>=0.5 + recency<=365d | 71 | 10 | 5 | +1.220R | +0.753R | PARTIAL POSITIVE (6 of 7 statistical-defensibility tests PASS) |
| R2-A canonical | V2 binding-variable flips (`vcp.tightness_days_required +16`); composite>=0.5 + recency<=365d | 65 | 40 | 9 (22.5% wr) | -1.086R | -0.782R | NEGATIVE |
| **R2-D canonical** | **V2 binding-variable flips (`vcp.adr_min_pct +11`); composite>=0.5 + recency<=365d** | **4** | **1** | **1 (100% wr)** | **+0.800R** | **n/a (N=1)** | **INSUFFICIENT SAMPLE (DIRECTIONAL POSITIVE color)** |

### 2.1 Substrate-depth comparison

Substrate depth (raw W primary verdicts -> post-canonical-filter actionable patterns):

| Cohort | Unique tickers | Raw W primary verdicts (composite>=0.5) | After 5-BD adjacency merge | After recency filter | Substrate density (final/raw %) |
|---|---|---|---|---|---|
| D2 EXPANDED | 88 (S&P 500 subset) | ~600+ | ~520 | 71 | ~12% |
| R2-A canonical | 7 (FRO/KOD/NAT/OII/RLMD/SEI/TROX) | ~500+ | ~450 | 65 | ~13% |
| **R2-D canonical** | **4 (AMX/GLNG/STNG/XENE)** | **132** | **127** | **4** | **~3%** |

The R2-D substrate density is **~4x thinner** than R2-A or D2 EXPANDED. This is the load-bearing finding for the INSUFFICIENT SAMPLE classification: the V2 binding-variable `vcp.adr_min_pct +11` cohort SELECTS a 4-ticker substrate where most historical W patterns fall OUTSIDE the 365-day recency filter when keyed to that cohort's asof_dates. The recency filter retains only 4 STNG patterns; AMX / GLNG / XENE have ZERO W primaries within 365 days of their respective asof_dates.

### 2.2 Cross-cohort interpretation per gotcha #33 BINDING

The dispatch brief section 6.5 (superseded by Amendment 1 A1.3) prescribed a 2x2 cross-cohort verdict matrix:

| R2-A E result | R2-D E result | Cross-cohort verdict |
|---|---|---|
| NEGATIVE | POSITIVE/PARTIAL POSITIVE | tightness_days_required-SPECIFIC |
| NEGATIVE | NEGATIVE | SYSTEMIC across V2 binding variables |
| NEGATIVE | AMBIGUOUS | weak; recommend R2-E |
| NEGATIVE | INSUFFICIENT SAMPLE | (brief: reduce thresholds OR widen recency) |

Per Amendment 1 A1.3 LOCK: R2-D is in the **INSUFFICIENT SAMPLE** quadrant. The Amendment FORBIDS the "reduce thresholds OR widen recency" escape hatch because doing so would (a) violate the canonical evaluation cohort discipline that both R2-A and D2 honor; (b) trigger gotcha #33 cohort-substitution prohibition. The defensible disposition is:

**The cross-cohort discrimination test is DEFERRED.** R2-D establishes only that:
1. The vcp.adr_min_pct binding-variable cohort substrate is ~4x thinner than R2-A's (a fact about V2 selection mechanics that the brief did not anticipate).
2. On the available 4-pattern substrate, both Ruleset E (1 winner at +0.800R) and Ruleset F (3 winners at +0.122R mean) produce DIRECTIONAL POSITIVE signals. These are insufficient to discriminate "systemic NEGATIVE" from "tightness_days_required-specific NEGATIVE."

Future R2-* dispatches should target **proximity_max_pct +5** OR **orderliness_max_bar_ratio +1** (the remaining V2 binding variables per dispatch brief section 11.2) to obtain a discriminating substrate.

---

## 3 Per-ruleset detail

| Ruleset | Patterns | Triggered | Closed | Closed-and-profitable | Open | Win-rate | Mean R closed | Mean R triggered |
|---|---|---|---|---|---|---|---|---|
| A_minervini_trail_ma | 4 | 4 | 0 | 0 | 4 | n/a | n/a | -0.060R |
| B_fixed_R_multiple | 4 | 4 | 0 | 0 | 4 | n/a | n/a | -0.060R |
| C_close_below_50d | 4 | 4 | 0 | 0 | 4 | n/a | n/a | -0.060R |
| D_minervini_stage2_progression | 4 | 4 | 0 | 0 | 4 | n/a | n/a | -0.060R |
| **E_oneil_cup_with_handle_measured_move** | 4 | 4 | **1** | **1** | 3 | **100%** | **+0.800R** | +0.023R |
| **F_qullamaggie_momentum_burst** | 4 | 4 | **3** | **3** | 1 | **100%** | **+0.122R** | +0.056R |

### 3.1 Open-at-data-tail dominance

All 4 STNG patterns triggered across all 6 rulesets (100% trigger rate) -- the entry trigger fires on the first close > center_peak_price after `effective_asof_date`, and all 4 patterns triggered between 2026-04-28 and 2026-04-29 (closely-clustered entries).

Of the 24 emitted trades, **20 remain OPEN at the data tail (2026-05-26)** because:
- Rulesets A/B/C/D have not hit their respective exit conditions (no trail-MA break / no fixed-R multiple / no close-below-50d / no Stage 2 progression failure) in the 18-19 sessions since entry.
- Ruleset E (O'Neil measured-move target) hit the measured-move target only on STNG-2025-05-22 (composite 0.7667, the highest-composite pattern) at +0.800R after 5 sessions; the other 3 STNG patterns remain open.
- Ruleset F (Qullamaggie momentum-gate fail at session 6) fired the momentum-gate exit on 3 of 4 patterns at +0.105R / +0.157R / +0.104R; STNG-2026-01-05 (the most-recent pattern, composite 0.6481) remains open.

### 3.2 STNG-2025-05-22: the headline-positive pattern

The single closed-and-profitable Ruleset E trade is STNG-2025-05-22 (composite 0.7667; trough_2 2025-06-30; days_t2_to_asof = 298; entry 2026-04-28; exit 2026-05-05; +0.800R via target_measured_move; max peak +1.026R; max drawdown +0.226R off peak).

This is the highest-composite W primary verdict in the R2-D fixture. The +0.800R / 100% win-rate / 5-session-hold profile is consistent with O'Neil cup-and-handle measured-move semantics on a confirmed W breakout. However, **N=1 closed is sub-threshold for any defensible PARTIAL POSITIVE claim on Ruleset E**.

### 3.3 Ruleset F's 3-of-3 momentum-gate exits

Ruleset F (Qullamaggie momentum-burst) closed 3 of 4 patterns with the `momentum_gate_fail` exit at session 6 (post-scale-out semantics). The 3 closed trades:
- STNG-2025-04-04 at +0.105R
- STNG-2025-05-22 at +0.104R
- STNG-2025-08-11 at +0.157R

All 3 are scale-out-weighted R-multiples reflecting a partial scale-out at 1R + final exit at the momentum-gate trigger. Mean +0.122R / 100% win-rate; std 0.030R (low dispersion -- consistent with a single-ticker substrate).

**Ruleset F technically meets PARTIAL POSITIVE thresholds in isolation** (>=3 closed-and-profitable + mean-R > 0 + 100% win-rate). However, per gotcha #33 BINDING, the headline verdict cannot use F's stats to claim "vcp.adr_min_pct +11 cohort produces PARTIAL POSITIVE for Ruleset F" because the cohort is a 4-pattern STNG single-ticker substrate. The case study is real but the generalization is forbidden.

### 3.4 Comparison with R2-A E NEGATIVE

R2-A's Ruleset E on N=65 (7 unique tickers) produced 22.5% win-rate / +mean R -1.086R / 95% CI [-1.377R, -0.782R] / P(mean>0)=0.0000. NEGATIVE was the headline verdict.

R2-D's Ruleset E on N=4 (1 unique ticker) produced 100% win-rate (N=1 closed) / +0.800R / no defensible CI. DIRECTIONAL POSITIVE on a single-pattern observation.

These two data points are NOT directly comparable because:
- Substrate size differs by ~16x (4 vs 65).
- Substrate ticker diversity differs (1 vs 7).
- The cross-cohort consistency claim requires comparable cohort sizes to discriminate sampling variance from systematic effect.

A future R2-* dispatch with N >= 20 (per gotcha #33's "statistically thin" threshold) is needed to perform the discrimination test.

---

## 4 Cohort generation provenance

### 4.1 Brief discrepancy disclosure (Amendment 1 A1.1)

The dispatch brief stated `sweep_point=1` + "11 watch->aplus flips" -- but the V2 sensitivity summary table at line 116 of the source artifact (`exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`) shows `vcp.adr_min_pct`'s +11 max_delta_aplus binding signal is at **sweep_point=2.0** (NOT 1). At sweep_point=1 the section emits 15 watch->aplus flips identical to R2-A's `vcp.tightness_days_required` cohort because adr_min_pct=1.0 is more relaxed than the +11 binding sweep_point. At sweep_point=2.0 the section emits exactly 11 flips matching the brief's count contract.

**The implementer used sweep_point=2.0** as the binding interpretation (the 11-flip-count contract is the binding signal; the sp=1 prescription was a brief-authoring error). Naming reflects this throughout (`R2D_SWEEP_POINT=2.0` FLOAT; cohort CSV `r2d_adr_min_pct_sp2_0.csv`; cohort_label `r2d_vcp_adr_min_pct_sp2_0`).

The brief's Amendment 1 (appended in the R1 Codex fix bundle) supersedes all sp=1 references; cross-references are recorded in section A1.5 of the brief.

### 4.2 Cohort derivation chain

| Stage | Count | Filter applied |
|---|---|---|
| Raw flips (V2 sensitivity drill-down vcp.adr_min_pct section) | 11 | sweep_point=2.0 AND watch->aplus |
| Cohort CSV after dedup by (ticker, asof_date) | 4 | (AMX/GLNG/STNG/XENE) |
| pattern_cohort_evaluator double_bottom_w raw verdicts | 1559 | per-window scoring |
| Composite>=0.5 W primary verdicts | 132 | pattern_cohort_evaluator filter |
| Post 5-BD adjacency merge (per-ticker, per-trough_1_date dedup) | 127 | merge_adjacent_troughs |
| **Canonical evaluation cohort (post recency<=365d filter)** | **4** | filter_recent_patterns; ALL STNG |

The 132 -> 4 collapse is driven by the recency filter: 3 of 4 cohort tickers (AMX, GLNG, XENE) have ZERO W primaries with `trough_2_date` within 365 calendar days of their respective `max_observed_asof_date`. Only STNG yields recency-passing W primaries.

### 4.3 Architecture: sibling-module strategy

Per dispatch brief section 1.2 LOCK, R2-D ships a sibling module set at `research/harness/r2d_adr_min_pct/` mirroring R2-A's `research/harness/r2a_tightness_days_required/` template:
- `cohort_csv.py` (565 lines; ported from R2-A with R2-D-specific constants: sweep_point=2.0 FLOAT, 11 EXPECTED_FLIPS, 4 EXPECTED_TICKERS, etc.)
- `regenerate_cohort.py` (argparse-driven entrypoint with `--allow-non-canonical-paths` flag per Codex R1.M#6)
- `__init__.py` (module docstring + brief discrepancy disclosure)

The common-parser refactor (R2-A + R2-D + future R2-* sharing a parametrized base) is banked as a **V2 candidate** per dispatch brief section 1.2 LOCK.

---

## 5 Discipline preservation

- **ZERO Co-Authored-By footer trailer drift** (~558+ cumulative streak through R2-A merge `634cc9f`; R2-D adds 5 commits all clean).
- **ZERO production swing/ writes** (the D2 6-ruleset CLI subcommand at `python -m research.harness.w_bottom_ruleset_comparison.run` was reused verbatim; no new production CLI surface).
- **ZERO new Schwab API calls** at backtest time (L2 LOCK preserved + reinforced via 3 NEW R2-D source-grep tests).
- **Schema v21 unchanged** (no migrations).
- **D2 harness REUSED verbatim** (6 byte-stability tests pass; `research/harness/w_bottom_ruleset_comparison/` unchanged from main).
- **R2-A modules FROZEN** (3 byte-stability tests pass; `research/harness/r2a_tightness_days_required/` unchanged from main; sibling-module strategy LOCK preserved).
- **ASCII discipline complete** (all NEW R2-D files: `cohort_csv.py` / `regenerate_cohort.py` / `__init__.py` / 4 test files / cohort.json / cohort CSV / audit JSON / smoke artifact / findings doc / return report / brief amendment).
- **Pre-flight archive refresh** applied operator-authorized at session start (AMX/GLNG/STNG/XENE via yfinance period='max' through 2026-05-26; per brief section 1.5 + R2-A precedent).
- **L6 caveat (gotcha #26)**: forward-walk bars come from CURRENT archive; may differ from V1 contemporaneous archive state at pattern_cohort_evaluator smoke time. The 4-pattern STNG substrate is too thin for this drift to materially affect the verdict.

---

## 6 V2 candidates banked

Per cumulative discipline (CLAUDE.md V1-simplification-banking discipline):

1. **Common-parser refactor (dispatch brief section 1.2 banking)**: post-R2-D ship, the operator MAY pivot to a refactor that pulls R2-A + R2-D common cohort_csv.py parser logic into a `research/harness/cohort_extractors/v2_sensitivity_drilldown.py` shared module + R2-A + R2-D + future R2-* become thin parametrized wrappers. NOT in scope for R2-D; banked.

2. **Byte-stability vs merge-base (Codex R2.m#2 / R1.m#2 banking)**: the byte-stability tests for D2 harness + R2-A modules compare to `main` HEAD (R2-A precedent). For long-lived branch review stability, prefer merge-base comparison. V2 hardening candidate.

3. **Pattern Pass-2 template matching empty (gotcha #28 / #29 family)**: pattern_cohort_evaluator smoke shows `template_match_score=None` across ALL 1559 emitted double_bottom_w verdicts (cache-empty per exemplar OHLCV pre-fetch limitation). Composite_score collapses to geometric_score only. Banked V2 dependency: extend `_step_exemplar_ohlcv` pipeline step OR pre-fetch exemplar tickers operationally before R2-* dispatches. R2-D verdict is **NOT materially affected** because the canonical evaluation cohort is N=4 STNG-only; template matching would not have rescued additional tickers (AMX/GLNG/XENE have ZERO W primaries within the recency window regardless of template scoring).

4. **Bootstrap CI on R2-D's R distribution (brief section 6.4 ask)**: with N=1 closed for Ruleset E and N=3 closed for Ruleset F, bootstrap CI is undefined / unreliable. The brief's bootstrap-CI request is implicitly contingent on N >= 10 closed (per D2 Amendment 5.3 methodology); R2-D's N=1 and N=3 trip the gotcha #33 cohort-size gate. Banked as: a future R2-* dispatch with N >= 20 closed-and-profitable per ruleset can run the bootstrap re-evaluation.

5. **Thicker-substrate cross-cohort discrimination (Amendment 1 A1.3 deferred test)**: R2-D could not answer the cross-cohort systemic-vs-cohort-specific question. Banked: future R2-E (`proximity_max_pct +5`) or R2-F (`orderliness_max_bar_ratio +1`) dispatch with the same harness architecture (sibling module pattern; same canonical filter; same 6-ruleset comparison) should reveal whether the cohort-specific NEGATIVE pattern persists.

---

## 7 Codex MCP adversarial review summary

| Round | Critical | Major | Minor | Verdict |
|---|---|---|---|---|
| R1 | 0 | 6 | 2 | ISSUES_FOUND |
| R2 | 0 | 0 | 4 | NO_NEW_CRITICAL_MAJOR |

**Cumulative: 0 CRITICAL + 6 MAJOR + 6 MINOR. ALL MAJOR resolved in-place; 4 of 6 MINOR resolved in-place; 2 BANKED (R1.m#2 byte-stability vs main per R2-A precedent; R2.m#4 Codex sandbox cannot run pytest = non-actionable).**

R1 surfaced 6 MAJOR findings that escaped pre-Codex review:
- M#1: brief sweep_point reconciliation (sp=1 -> sp=2.0)
- M#2: INSUFFICIENT SAMPLE pre-commit per gotcha #33
- M#3: fixture identity lock (N=4 + STNG-only + exact trough/peak dates)
- M#4: audit JSON cohort_selection_method + v2_binding_variable
- M#5: canonical source SHA/size validation in wrapper
- M#6: --allow-non-canonical-paths CLI flag

These map to a **NEW writing-plans / brief-authoring discipline lesson** (banked for future R2-* dispatches): when authoring an R2-* dispatch brief, the brief MUST verify the canonical sweep_point against the V2 sensitivity SUMMARY TABLE (not just the drill-down section header) before publishing the prescriptive count + sweep_point pair. Future briefs should explicitly cross-reference the summary table's `max_delta_aplus` cell to confirm the binding sweep_point.

**41st cumulative C.C lesson #6 validation NOTABLE** (Codex caught 6 real MAJOR defects despite pre-Codex application of all 17 expansion candidates; the brief-authoring error at A1.1 + the architectural fixture-identity-lock gap at M#3 are the most consequential surfaces this round; both bank as cumulative lessons for future R2-* + V2 dispatches).

---

## 8 Conclusions + next-arc operator decisions

### 8.1 The cross-cohort systemic-vs-cohort-specific question is DEFERRED

R2-A NEGATIVE (N=65) vs R2-D INSUFFICIENT SAMPLE (N=4) does NOT discriminate between:
- (a) R2-A's NEGATIVE is unique to `vcp.tightness_days_required +16`
- (b) R2-A's NEGATIVE is systemic across V2 binding variables

A future R2-* dispatch against **`vcp.proximity_max_pct +5`** OR **`vcp.orderliness_max_bar_ratio +1`** is required. The implementer recommends:

1. **R2-E: vcp.proximity_max_pct +5** -- next-largest remaining binding variable per brief section 11.2 ordering. Substrate density unknown; may also collapse to a thin cohort. Pre-flight cohort_size analysis at slice 1 should be the first sanity check.
2. If R2-E also INSUFFICIENT SAMPLE, **investigate WHY V2 binding-variable selection produces thin W-pattern substrates** -- this is itself a methodologically informative finding (e.g., V2 selection mechanic may correlate with regimes where W patterns are scarce; or recency<=365d may be over-restrictive for selection-biased cohorts).
3. **Alternative arc**: drop the cross-cohort dimension entirely and investigate market-conditions / other-gates-not-enumerated per dispatch brief precedent. CLAUDE.md preserves this enumeration in the cumulative status line.

### 8.2 STNG as a case study (informational; NOT a defensible generalization)

STNG produced 4 W primary verdicts within the 365-day recency window:
- 2025-04-04 / 2025-05-13 / 2025-05-22 (composite 0.5)
- 2025-05-22 / 2025-06-18 / 2025-06-30 (composite 0.7667; the headline POSITIVE on Ruleset E)
- 2025-08-11 / 2025-09-15 / 2025-10-14 (composite 0.5)
- 2026-01-05 / 2026-03-04 / 2026-03-17 (composite 0.6481)

All 4 triggered between 2026-04-28 and 2026-04-29 (effective_asof = 2026-04-24 + 1 BD). Ruleset E hit the measured-move target on the highest-composite pattern (2025-05-22); Ruleset F's momentum-gate fired at session 6 on 3 of 4 patterns. This is consistent with STNG's recent (2026-04 to 2026-05) breakout pattern but does NOT establish ruleset-level generalization.

### 8.3 Cohort-validity discipline LOCKED for future R2-* dispatches

Gotcha #33 third canonical application (post D2 Amendment 3 + R2-A second application) reinforces the discipline: future R2-* dispatch briefs MUST pre-commit the canonical evaluation cohort + the INSUFFICIENT SAMPLE escape hatch + the cohort-substitution prohibition AT THE BRIEF-AUTHORING PHASE. The R2-D brief's omission of these (Amendment 1 had to retrofit them) is a brief-authoring lesson worth banking.

---

*End of findings doc. R2-D cohort INSUFFICIENT SAMPLE for the cross-cohort systemic-vs-cohort-specific test; DIRECTIONAL POSITIVE color on N=1 closed Ruleset E + N=3 closed Ruleset F as case study; deferred discrimination test to future R2-* against thicker substrate. Discipline preservation + Codex MCP review preserve the ~558+ ZERO Co-Authored-By cumulative streak through the dispatch.*
