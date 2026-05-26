# R2-A Backtest Findings: V2 OHLCV `vcp.tightness_days_required +16` Cohort 6-Ruleset Comparison

**Date:** 2026-05-26
**Branch:** `applied-research-r2a-tightness-days-required-cohort-backtest`
**Smoke artifact:** [`exports/research/w-bottom-ruleset-comparison-20260525T224203Z/`](../exports/research/w-bottom-ruleset-comparison-20260525T224203Z/)
**Upstream cohort:** [`exports/research/pattern-cohort-detection-20260526T081400Z/`](../exports/research/pattern-cohort-detection-20260526T081400Z/)
**Cohort CSV:** [`exports/research/cohorts/r2a_tightness_days_required_sp1.csv`](../exports/research/cohorts/r2a_tightness_days_required_sp1.csv) (7 unique (ticker, asof_date) rows)
**Audit JSON:** [`exports/research/cohorts/r2a_tightness_days_required_sp1.flips_audit.json`](../exports/research/cohorts/r2a_tightness_days_required_sp1.flips_audit.json) (15 raw flips + source SHA-256)
**Cohort fixture:** [`tests/fixtures/research/r2a_tightness_days_required/cohort.json`](../tests/fixtures/research/r2a_tightness_days_required/cohort.json) (N=65 canonical W primary verdicts)

---

## 1 Headline verdict: **NEGATIVE** on the canonical R2-A evaluation cohort

Ruleset E's PARTIAL POSITIVE verdict from D2 (bias-free S&P 500 cohort; mean R +1.220R / 95% CI lower +0.753R / 5 closed-and-profitable on N=71 EXPANDED) does **NOT** generalize to the V2 OHLCV binding-variable cohort.

**R2-A canonical evaluation cohort** (composite>=0.5 + recency<=365d; mirrors D2 Amendment 5 EXPANDED filter per dispatch brief §6.4):

- N=65 historical W patterns across 7 tickers (FRO=7, KOD=14, NAT=7, OII=5, RLMD=11, SEI=10, TROX=11)
- 62 of 65 patterns triggered (95% trigger rate; 3 untriggered)
- Ruleset E: **9 closed-and-profitable / 40 closed / 22.5% win-rate / mean R closed -1.086R / std 0.961R**
- Ruleset E Bootstrap 95% CI on mean R closed: **[-1.377R, -0.782R]** — entirely below zero
- P(mean R > 0 | bootstrap) = 0.0000

| Verdict gate (§6.5) | E | D | F |
|---|---|---|---|
| mean-R closed > 0 | -1.086R FAIL | -1.316R FAIL | -0.154R FAIL |
| win-rate >= 25% (PARTIAL POSITIVE) | 22.5% FAIL | 0.0% FAIL | 0.0% FAIL |
| closed-and-profitable >= 3 (PARTIAL POSITIVE) | 9 PASS | 0 FAIL | 0 FAIL |
| **PARTIAL POSITIVE threshold met?** | NO (2 of 3 fail) | NO (3 of 3 fail) | NO (3 of 3 fail) |

ALL of {D, E, F} fail PARTIAL POSITIVE thresholds → **NEGATIVE** verdict per dispatch brief §6.5.

---

## 2 Cross-cohort comparison: PARTIAL POSITIVE → NEGATIVE generalization failure

| Cohort | Definition | N | E closed-and-profitable | E mean R closed | E 95% CI lower | Verdict |
|---|---|---|---|---|---|---|
| D1 post-refresh (`131423Z`) | Hand-curated +67 watch→aplus from V2 `vcp.tightness_range_factor=1.005`; recency<=60d | 12 | n/a (E not tested at D1) | n/a | n/a | NEGATIVE (D1 brief criteria) |
| D2 Companion 2 canonical | Bias-free S&P 500; composite>=0.5 + recency<=120d | 26 | 3 | +1.208R | +0.464R | PARTIAL POSITIVE |
| D2 EXPANDED Amendment 5 | Bias-free S&P 500; composite>=0.5 + recency<=365d | 71 | 5 | +1.220R | +0.753R | PARTIAL POSITIVE |
| **R2-A canonical** | **V2 binding-variable flips (sweep_point=1, watch→aplus); composite>=0.5 + recency<=365d** | **65** | **9** | **-1.086R** | **-0.782R** | **NEGATIVE** |

**Cross-cohort interpretation:** R2-A E reaches NEGATIVE while D2 E PARTIAL POSITIVE → E is **cohort-specific to bias-free S&P 500 detection**, NOT robust to selection-biased V2-binding-variable cohort enrichment. Per gotcha #33 cohort-validity-vs-verdict-criteria discipline, the canonical evaluation cohort is held FIXED at the EXPANDED filter (composite>=0.5 + recency<=365d) so the comparison is apples-to-apples on the evaluation lens; only the cohort SELECTION mechanism differs.

The asymmetric P&L distribution is striking: **R2-A E winners average +0.512R / R2-A E losers average -1.550R** (winners hit measured-move target around +0.5R; losers fall through max(trough_2 × 0.99, entry × 0.92) stop). Contrast D2 EXPANDED E winners with mean +1.22R — D2's winners had MEANINGFULLY HIGHER R than R2-A's, suggesting that V2-selection-biased tickers' historical Ws produce truncated upside even when they trigger.

---

## 3 Per-ticker concentration analysis (Codex R1 follow-through)

Per Codex R1 M#8 + M#9 + dispatch brief §6.5 (gotcha #33), report whether per-cohort verdict is dominated by 1-2 tickers vs broadly distributed:

| Ticker | E closed | E winners | E mean R | Note |
|---|---|---|---|---|
| FRO | 3 | 3 | +0.768R | All three triggered patterns hit measured-move target |
| KOD | 14 | 3 | -0.729R | 3 of 14 closed-and-profitable; 11 losers dragging mean negative |
| OII | 1 | 1 | +0.862R | Single closed trade, winner |
| RLMD | 11 | 2 | -1.282R | Heavy loser concentration |
| TROX | 11 | 0 | -2.027R | Zero winners; deepest mean loss |
| NAT | 0 | 0 | n/a | All 7 patterns still open at data tail |
| SEI | 0 | 0 | n/a | All 10 patterns still open at data tail |

**Unique tickers contributing E winners: 4 of 7** (FRO, KOD, OII, RLMD). The winning ticker count crosses the >=3-tickers heuristic enumerated in the Codex R1 M#9 commitment, but the per-ticker R distribution is highly heterogeneous (FRO/OII strongly positive; KOD/RLMD/TROX strongly negative). NAT + SEI contribute ZERO closed trades because their patterns are concentrated near the recent (2026-05-08 / 2026-05-12) asof boundary; forward bars beyond 2026-05-22 (current data) are insufficient for the 60-BD trigger search window or the trail-exit logic to fire.

This is the canonical signature of cohort selection-bias laundering risk (Codex R1 M#7) — even WITH per-ticker breakdown, the verdict is mechanically driven by KOD + RLMD + TROX (36 of 40 closed E trades) whose poor outcomes outweigh FRO + OII's strong winners.

---

## 4 Cohort-validity discipline applied (gotcha #33)

Per cumulative CLAUDE.md gotcha #33 (cohort-validity-vs-verdict-criteria):

- **Cohort selection method:** `v2_binding_variable_flips` (V2 OHLCV sensitivity drill-down; vcp.tightness_days_required section at sweep_point=1; old_bucket=watch → new_bucket=aplus). Recorded in cohort_csv module constants + audit JSON `cohort_label` + dispatch brief §7.1.
- **Cohort transformation:** The 15 V2 flip events identify 7 candidate TICKERS at specific asof snapshots. Downstream pattern_cohort_detect enumerates ALL Phase 13 chart-shape verdicts on those (ticker, asof) snapshots; the D1 cohort extractor dedupes by (ticker, trough_1_date), applies 5-BD adjacency merge + recency<=365d filter → N=65 backtest cohort. The backtest cohort is therefore **historical W patterns on V2-selected tickers, NOT the 15 V2 flip events themselves**.
- **Generalization claim scope:** R2-A's NEGATIVE verdict applies ONLY to the V2-binding-variable-selected ticker substrate evaluated through D2's walk-forward pipeline. It does NOT imply that E is universally NEGATIVE; D2 EXPANDED's PARTIAL POSITIVE remains intact on its bias-free S&P 500 cohort.
- **No cohort substitution attempted:** gotcha #33 prescribes "headline verdict MUST be on the cohort with strongest research-question-fit, NOT the cohort that produces the most favorable result." The canonical R2-A evaluation cohort (composite>=0.5 + recency<=365d) is held fixed; alternative scopes (composite>=0.7 + recency<=60d = N=3; composite>=0.5 + recency<=120d = N=21) are documented in the cohort scope analysis but NOT used to substitute the verdict.

---

## 5 Cohort scope analysis (pre-backtest; dispatch brief §1.3)

From the 3391 raw double_bottom_w verdicts produced by `pattern_cohort_detect` against the R2-A 7-ticker / 15-flip cohort CSV:

| Filter | N patterns | N tickers |
|---|---|---|
| composite>=0.7 + no recency | 292 | 7 |
| composite>=0.7 + recency<=60d | 3 | 3 |
| composite>=0.7 + recency<=120d | 6 | 5 |
| composite>=0.7 + recency<=365d | 17 | 6 |
| composite>=0.5 + no recency | 1193 | 7 |
| composite>=0.5 + recency<=60d | 13 | 7 |
| composite>=0.5 + recency<=120d | 21 | 7 |
| **composite>=0.5 + recency<=365d (CANONICAL)** | **65** | **7** |

Selection rationale for the canonical evaluation cohort: per dispatch brief §6.4 + §10, R2-A uses the EXPANDED filter mirroring D2 Amendment 5 ratification. This holds the evaluation lens constant across R2-A vs D2 comparisons; only the cohort SELECTION mechanism differs (V2-binding-variable flips vs bias-free S&P 500 detection).

---

## 6 Bootstrap CI methodology

Bootstrap CI on E's mean R closed (mirrors D2 Amendment 5.3 methodology):
- N_resamples = 10,000
- Resample: random.seed(42); for each resample, draw 40 R values with replacement; compute mean
- Sort resampled means; 2.5th percentile = lower CI; 97.5th percentile = upper CI
- P(mean > 0) = fraction of resampled means > 0

**Result: 95% CI = [-1.377R, -0.782R]; P(mean > 0) = 0.0000.**

Both CI bounds are below zero. The probability that E's true mean R on this cohort is positive is statistically indistinguishable from zero. Combined with the criterion-based verdict (mean R -1.086R < 0; win-rate 22.5% < 25%), the NEGATIVE classification is statistically robust.

---

## 7 R2-A specific architectural observations

### 7.1 Smoke runtime + cohort cardinality

- Smoke runtime: 3.7s (390 trades = 65 patterns × 6 rulesets)
- pattern_cohort_detect runtime: not measured separately; 3391 raw verdicts emitted across 7 (ticker, asof) inputs (mean 484 W verdicts per snapshot due to long OHLCV history for OII = 12745 bars covering 50+ years of data)
- D2 harness reused verbatim (asserted by 6 byte-stability tests); ZERO modifications to `research/harness/w_bottom_ruleset_comparison/`

### 7.2 Pre-flight archive refresh provenance (Codex R1 M#10)

- FRO archive: stale at 2026-05-14 → refreshed via yfinance `period='max'` → last bar 2026-05-22, 6236 rows
- NAT archive: stale at 2026-05-14 → refreshed via yfinance `period='max'` → last bar 2026-05-22, 7206 rows
- KOD / OII / RLMD / SEI / TROX archives: current at 2026-05-22 pre-dispatch; no refresh needed
- All 7 tickers use legacy `.parquet` (no Shape A `.yfinance.parquet` files present); V2 reader falls through to legacy correctly

**Caveat:** Pre-flight refresh changes forward bars relative to the V2 sensitivity artifact's original archive state; the backtest is therefore "current-state walk-forward" not "exact-V2-artifact reproduction." This is acceptable because the research question is about whether D2 E generalizes to the V2-selected ticker substrate, not about reproducing the V2 evaluator's per-criterion arithmetic.

### 7.3 Exemplar pattern detection: 4 of 7 tickers produce closed E winners

Per-ticker E winner count:
- FRO: 3 / 3 closed (100% win rate on this ticker; very small sample)
- KOD: 3 / 14 closed (21% win rate)
- OII: 1 / 1 closed (100%; single sample)
- RLMD: 2 / 11 closed (18%)
- TROX: 0 / 11 closed
- NAT: 0 closed (all open)
- SEI: 0 closed (all open)

The unique-winning-tickers count (4 of 7) crosses the dispatch brief's implicit >=3-tickers threshold for non-concentration. However the heterogeneity is severe: 67% of closed E winners (6 of 9) come from FRO + KOD, and TROX contributes 11 losers with mean R -2.03R that drag the aggregate negative. This is consistent with the selection-bias mechanism: V2's tightness_days_required binding variable identifies tickers with mid-range trading-density profiles (operator's vcp.tightness flag); the historical W patterns on those tickers have a different drawdown distribution than the bias-free S&P 500 universe.

---

## 8 Conclusions + research-question implications

1. **Headline:** R2-A NEGATIVE → D2 Ruleset E's PARTIAL POSITIVE does NOT generalize across cohort definitions. E's verdict is **cohort-specific to the bias-free S&P 500 detection-based cohort**, not robust to V2-binding-variable selection-biased cohort enrichment.

2. **Methodological signal:** Cross-cohort verdict inconsistency is a STRONG signal that any single-cohort PARTIAL POSITIVE result deserves wider robustness testing before being treated as production-evidence. D2's bias-free PARTIAL POSITIVE remains valid for the specific S&P 500 universe it tested; the V2-binding-variable mechanism appears to select tickers with intrinsically different P&L distributions.

3. **Per-ticker concentration:** R2-A's NEGATIVE is NOT a thin-sample artifact — N=65 patterns / 40 closed E trades / 9 winners is a reasonable sample for E. The negative result is driven by ASYMMETRIC P&L (winners +0.5R average; losers -1.5R average) rather than by under-sampling.

4. **No cohort substitution:** Per gotcha #33, the verdict is held on the canonical EXPANDED filter (composite>=0.5 + recency<=365d). Sub-cohort exploration (composite>=0.7 → N=17; recency<=60d → N=13) is documented in §5 above but is NOT used to substitute the headline classification.

5. **V2 sensitivity binding-variable signal interpretation:** A V2 +16 max_delta_aplus from `vcp.tightness_days_required` identifies tickers where the V2 evaluator's threshold would loosen to admit watch-tier candidates as A+. The 15 flip events targeting 7 tickers do NOT correspond to backtest-positive trade opportunities; the V2 sensitivity framework measures classification-threshold-shift count, NOT actionable-trade-outcome quality (consistent with the prior R1 finding for `vcp.tightness_range_factor=1.005`).

6. **Next-arc operator decisions banked** (handed to orchestrator):
   - Pivot to a different V2 binding variable (e.g., `vcp.adr_min_pct +11`, `vcp.proximity_max_pct +5`, `vcp.orderliness_max_bar_ratio +1`) and test whether the cohort-specific-NEGATIVE pattern recurs;
   - Pivot to market-conditions investigation (per CLAUDE.md operator-paired next-arc enumeration);
   - Pivot to Phase 14 commissioning per Path B sequencing;
   - Pivot to archive refresh + re-run of the full V2 sensitivity (last refresh 2026-05-24) to test whether refreshed-archive flip events differ.

---

## 9 Codex MCP adversarial review chain summary (40th cumulative C.C lesson #6 validation)

| Round | Critical | Major | Minor | Resolution |
|---|---|---|---|---|
| R1 | 0 | 12 | 8 | 4 in-code (parser robustness + audit JSON); 6 deferred to findings doc layer (§3 + §4); 2 ACCEPTED with rationale |
| R2 | 0 | 8 | 3 | 5 in-code (layered verifier + canonical wrapper + heading regex + audit SHA + variable_name reuse); 3 ACCEPTED with rationale |
| R3 | 0 | 3 | 4 | 2 in-code (committed-artifact lock test + bypass removal); 2 in-docs (multiset wording + path POSIX); 1 ACCEPTED (code-fence detection); 1 ACCEPTED (atomicity) |
| R4 | 0 | 3 | 3 | 3 in-code (CSV row count + audit metadata + unconditional SHA lock); 3 in-code (docstring fix + flips list length + regen entrypoint) |
| R5 | 0 | 0 | 3 | 1 in-code (dead-code _H3_VARIABLE_REGEX removal); 2 BANKED as V2 candidates |

**Cumulative R1-R4: 26 MAJOR + 18 MINOR; ALL CRITICAL+MAJOR RESOLVED in-place or ACCEPTED with documented rationale.** R5 verdict: `NO_NEW_CRITICAL_MAJOR` — chain converged. 5 rounds total.

40th cumulative C.C lesson #6 validation **NOTABLE**:
- Codex caught REAL defects in cohort generation: (a) silent under-extraction risk on parser permissiveness (R1.M#2); (b) hardcoded column positions vulnerable to schema reorder (R1.M#4); (c) section-boundary bug when no h3 follows (R2.M#3); (d) line-anchored heading regex requirement for prose-defense (R2.M#4); (e) audit identity verification at the per-triple level (R2.M#1 + M#2).
- Pre-Codex review applied cumulative expansions #1-#11 BUT Codex still surfaced 12 R1 MAJOR + 8 R1 MINOR; the cohort-generation surface had unique parser-robustness vectors not covered by prior expansion patterns.
- ZERO production swing/ writes; L2 LOCK preserved + reinforced via 2 BINDING R2-A tests (test_r2a_module_no_schwab_or_yfinance_imports parametrized over 2 modules).

---

## 10 Caveats + L6 limitations

1. **Forward-walk uses CURRENT archive** (not V2-contemporaneous): pre-flight refresh of FRO + NAT changes forward bars vs the original V2 sensitivity artifact's archive state. This is acceptable for the research question (does E generalize?) but does NOT reproduce the V2 evaluator's per-criterion arithmetic. Banked as L6-style limitation per CLAUDE.md gotcha #26 (archive bar-content temporal mutation).

2. **NAT + SEI ZERO closed trades** at data tail: 7 + 10 = 17 patterns (26% of N=65) are still open. R2-A captures their pre-tail entry behavior but cannot evaluate their final R-multiple. The verdict is robust to this because (a) the 40 closed E trades constitute a 62% closure rate sufficient for bootstrap CI; (b) NAT + SEI open patterns are not pulling toward either positive or negative aggregate behavior.

3. **Selection bias acknowledged** per gotcha #33: R2-A's NEGATIVE applies ONLY to the V2-binding-variable-selected ticker substrate; it does NOT generalize to a broader population.

4. **R2-A cohort is SUPERSET of D1 cohort** (5-ticker overlap: KOD/NAT/OII/RLMD/TROX): the 2 NEW tickers vs D1 are FRO + SEI. D1's NEGATIVE verdict on hand-curated 12-pattern cohort (mean -0.18R unrealized) is directionally CONSISTENT with R2-A's NEGATIVE verdict on the broader composite>=0.5 + recency<=365d filter. The 6-ruleset comparison adds the D/E/F surface that D1 did not test.

5. **Statistical-defensibility tier (per D2 Amendment 5.5):**
   - Mean R closed: -1.086R (below zero) → FAILS positive-mean test
   - Win-rate: 22.5% → FAILS 25% threshold
   - N closed-and-profitable: 9 (>=3 → PASSES count threshold)
   - 95% CI lower bound: -0.782R (below zero) → FAILS lower-bound-positive test
   - P(mean > 0): 0.0000 → FAILS P-positive test
   - Sign test: 9 wins / 31 losses → p << 0.05 in favor of LOSS direction
   - N>=10: PASSES (N=40)
   - Tally: 2 of 7 tests pass (count + N>=10); 5 of 7 fail (mean / win-rate / CI / P-positive / sign)
