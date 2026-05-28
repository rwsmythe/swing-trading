# Applied Research Arc Closure -- W-Pattern Ruleset Investigation Family

**Canonical citation:** "2026-05-27 applied research arc closure" (commits `a43a921` through `bf7e071`; arc duration 2026-05-23 through 2026-05-27 PM #3).

**Status:** CLOSED. Operator-validated synthesis 2026-05-27 PM #3 (Turn H session post-G2 SHIPPED).

**Headline finding:** No tested ruleset (A_minervini_trail_ma through I_edwards_magee_classical_double_bottom; 9 named rulesets) produces robust positive portfolio expectancy across the substrates tested (D1, D2 Companion 2, D2 EXPANDED, R2-A, R2-D, V2-mechanic). The single tentative positive (E on D2 EXPANDED N=71 original; +1.220R; 6 of 7 statistical-defensibility tests PASS) failed substrate-freshness reproducibility when re-evaluated at G2 dispatch (N=71 -> N=42; +1.220R -> -0.800R). The arc has reached its methodological end-point at current substrate scale.

**Forward path:** Phase 14 temporal pattern detection + observation log infrastructure (commissioned 2026-05-27 PM #3; see `docs/phase14-commissioning-brief.md` Sec 2.5) eliminates the failure modes (gotchas #26 + #37) by architectural construction; accumulates substrate organically over months; enables future investigations against N >= 100+ patterns with frozen regeneration semantics.

---

## Sec 1 Arc framing + mission evolution

**Original operator goal (Turn G + earlier):** Identify threshold tweaks that expand the actionable candidate count (A+ population) at the daily pipeline output. The V2 OHLCV criterion-evaluator was built to answer this question.

**Joint hypothesis evolution (Turn H session):** The operator clarified the goal as joint: (a) expand the candidate population AND (b) apply a shape-specific ruleset derived from the available reference library to maintain or improve win/loss ratio. The arc tested this joint hypothesis across 12 sub-arcs.

**Why the joint hypothesis matters:** raising candidate count without preserving outcome quality is worse than useless. The arc's substantive work was investigating whether ANY combination of (V2-expanded population) + (canonical W-bottom ruleset) achieves positive expectancy.

**Final synthesis:** the joint hypothesis is NOT supported at the substrate scales and ruleset variants tested. This is a substantive answer, not a failed investigation.

---

## Sec 2 Arc map (chronological)

| # | Date | Commit | Sub-arc | Substrate | Result |
|---|---|---|---|---|---|
| 1 | 2026-05-23 | `a43a921` | V2 OHLCV criterion-evaluator executing-plans (5 NEW modules + CLI subcommand) | V2 universe 516 unique tickers | 5 binding variables identified all VCP-family (tightness_range_factor +75; tightness_days_required +16; adr_min_pct +11; proximity_max_pct +5; orderliness_max_bar_ratio +1) |
| 2 | 2026-05-24 PM | `c8f9612` | V2 full-reproduction investigation (H6 archive bar-content TEMPORAL mutation root cause) | V2 same | gotcha #26 banked; V2 evaluator confirmed CORRECT 3x via decisive counter-tests; 14 drift entries characterized as L4-style |
| 3 | 2026-05-25 | `e0a9edd` | D1 backtest (tightness_range_factor +75 hand-curated +67 cohort; tightness_range_factor=1.005) | 12 patterns | NEGATIVE-strict; 17 patterns / 5 triggered / 0 closed / -0.18R mean unrealized; classification gain (+75 max_delta_aplus) does NOT equal +75 actionable trades |
| 4 | 2026-05-25 PM | `d7387b8` | D2 6-ruleset comparison + Amendment 5 EXPANDED | D2 EXPANDED N=71 (bias-free S&P 500; composite>=0.5 + recency<=365d) | **E PARTIAL POSITIVE** mean R closed +1.220R / CI [+0.753R, +1.704R] / 6 of 7 statistical-defensibility tests PASS; **the single tentative positive of the arc** |
| 5 | 2026-05-26 | `634cc9f` | R2-A V2 vcp.tightness_days_required +16 cohort 6-ruleset | R2-A N=65 (7 tickers; FRO/KOD/NAT/OII/RLMD/SEI/TROX) | NEGATIVE; E mean R -1.086R / CI [-1.377R, -0.782R] / 22.5% win-rate; cohort-specific finding bounded D2 E's generalization scope (Amendment 6) |
| 6 | 2026-05-26 PM #2 | `7330628` | R2-D V2 vcp.adr_min_pct +11 cohort 6-ruleset | R2-D N=4 STNG-only | INSUFFICIENT SAMPLE per gotcha #33 third canonical application; substrate density ~3% vs peer ~13%; brief Amendment 1 sweep_point sp=1->sp=2.0 reconciliation (gotcha #34 first canonical application) |
| 7 | 2026-05-27 AM | `64e0099` | V2-selection-mechanic analytical investigation (5 V2 binding variables characterized) | 5 V2 substrates + D2 baseline reference | V2 substrates ENRICHED for W-pattern productivity per ticker (D_filt 7.2x-70x baseline 0.138); per-variable 3-axis profile tags lock; substrate "thinness" was small-T not low-W-incidence; gotcha #35 (substrate density metric disambiguation) banked; gotcha #36 (two-Codex-chain default) banked simultaneously |
| 8 | 2026-05-27 PM | `31fa281` | G2 W-bottom-derived ruleset backtest (3 NEW rulesets G/H/I; 9-metric scorecard) | R2-A N=65 + D2 EXPANDED N=42 | **Joint hypothesis NOT supported**; all 9 (ruleset, substrate) cells expectancy_R < 0 (range -3.13R to -0.146R); G_bulkowski tight-stop partially validated on avg_loss_R lever (1.55R->0.62R) but offset by win-rate + trigger conversion drops; D2 EXPANDED N=71->N=42 substrate-freshness reframe; gotcha #36 FIRST canonical application validated (chain #1 caught 3C+13M+12m pre-smoke) |
| 9 | 2026-05-27 PM #3 | `e1a4bdf` | Gotcha #37 banking (substrate-freshness sensitivity) | n/a | gotcha #37 BANKED extending gotcha #26 from per-bar to per-cohort-fixture membership TEMPORAL mutation |
| 10 | 2026-05-27 PM #3 | `bf7e071` | Phase 14 commissioning brief authored | n/a | Phase 14 commissioned with temporal log infrastructure as the forward improvement; deferral cleared |

---

## Sec 3 Per-ruleset per-substrate scorecard (canonical numerical table)

**Numerical values per gotcha #35 metric definitions:** expectancy_R = mean R closed (sum R per closed trade / N_closed); win_rate = N(R>0 closed)/N_closed; avg_loss_R = abs(mean(R) over closed losers).

| Ruleset | D1 +67 | D2 Companion 2 N=26 | D2 EXPANDED N=71 ORIG | D2 EXPANDED N=42 G2 | R2-A N=65 | R2-D N=4 STNG-only |
|---|---|---|---|---|---|---|
| A_minervini_trail_ma | n/a | n/a | n/a | tested; <0 | -0.234R / 0% / -0.234R | tested |
| B_fixed_R_multiple | n/a | n/a | n/a | tested; <0 | -1.316R / 0% / -1.316R | tested |
| C_close_below_50d | NEGATIVE-strict via DK + TROX | tested | tested | tested; <0 | tested; <0 | tested |
| D_minervini_stage2_progression | n/a | n/a | n/a | tested; <0 | -1.316R / 0% / -1.316R | tested; -0.06R triggered avg |
| **E_oneil_cup_with_handle_measured_move** | n/a | **+1.208R / N=3 closed-profit** (degenerate small-N) | **+1.220R / 5 closed-profit / CI [+0.753, +1.704]** (the tentative arc positive) | **-0.800R** (substrate-freshness reframe; gotcha #37 casualty) | -1.086R / 22.5% / -1.550R | +0.800R / N=1 closed (DIRECTIONAL POSITIVE only; gotcha #33 cohort substitution rejected) |
| F_qullamaggie_momentum_burst | n/a | tested | tested | tested; <0 | tested; <0 | +0.122R / 100% wr / N=3 closed (technical PARTIAL POSITIVE rejected per gotcha #33) |
| G_bulkowski_double_bottom (NEW G2) | n/a | n/a | n/a | <0 (G expectancy <0; avg_loss_R 0.560R vs E 1.576R; win_rate 0%) | <0 (avg_loss_R 0.618R vs E 1.550R; win_rate 2%; G's TIGHT-STOP HYPOTHESIS partially validated on avg_loss_R lever but offset) | n/a |
| H_oneil_double_bottom_base (NEW G2) | n/a | n/a | n/a | <0 (avg_loss_R 2.14R; trig_conv 0.29; DOMINATED across both substrates) | <0 (avg_loss_R 3.29R; trig_conv 0.38) | n/a |
| I_edwards_magee_classical (NEW G2) | n/a | n/a | n/a | <0 (avg_loss_R 0.623R; trig_conv 0.31) | <0 (avg_loss_R 0.557R; trig_conv 0.52) | n/a |

**Reading the table:** rows are rulesets; columns are substrates. Cell format: `expectancy_R / win_rate / avg_loss_R` where surfaced. Bold cells are the substantively interesting positives + the one substrate-freshness casualty. `n/a` = not tested or insufficient detail in arc artifacts at this aggregation level (per-trade detail available in respective smoke artifacts).

**Substantive consequence of the table:** ZERO cells achieve all three discipline gates simultaneously: (a) statistical defensibility (positive CI lower bound + N>=10 closed); (b) cohort-validity (gotcha #33 no-substitution); (c) substrate-freshness reproducibility (gotcha #26 + #37). The closest near-success (E on D2 EXPANDED N=71 ORIGINAL) failed (c) at G2 re-run.

---

## Sec 4 Substantive findings synthesis (descriptive per gotcha #33 LOCK)

### Finding 1 -- The original D2 Amendment 5 PARTIAL POSITIVE finding is methodologically suspect

E on D2 EXPANDED N=71 ORIGINAL: +1.220R / 5 closed-and-profitable / CI [+0.753R, +1.704R] / 6 of 7 statistical-defensibility tests PASS. This was the headline finding of the arc pre-G2.

At G2 dispatch (2026-05-27 PM; merge `31fa281`), the same E logic + same D2 cohort fixture + same canonical filter yielded N=42, NOT N=71 (Brief Amendment 1). The 29 missing patterns had been carrying disproportionate weight in the original +1.220R signal. On the actual SHA-locked N=42 fixture, E's expectancy is -0.800R -- sign-flipped from the original anchor. The cohort had drifted because `max_observed_asof_date` timestamps were regenerated for some verdicts in the interim.

**This is not "E was wrong"** -- the original arithmetic was correct against the original substrate. It is that the substrate is not stable enough for the finding to be reproducible. Banked as gotcha #37.

### Finding 2 -- G_bulkowski's tight-stop hypothesis is partially validated on the avg_loss_R lever

G's avg_loss_R is meaningfully lower than E's on both substrates: R2-A G 0.618R vs E 1.550R (a 60% reduction); D2 G 0.560R vs E 1.576R (a 64% reduction). The tighter trough_2-relative stop achieves what brief Sec 1.1 + Sec 6(g) anticipated -- it materially reduces per-loss magnitude.

But the gain is offset by sharply lower win-rate (G: 2%/0% vs E: 23%/28%) + lower trigger conversion (G: 0.85/0.69 vs E: 0.95/0.90). Net expectancy_R remains below zero.

**This is a real methodological signal:** stop placement matters; tight stops do reduce per-loss magnitude; but the win-rate cost was not compensated by upside magnitude at the substrate sizes tested. Future arcs investigating tight-stop variants should expect this trade-off.

### Finding 3 -- H_oneil + I_edwards_magee dominated by other rulesets

H_oneil's 8% entry-relative + SMA50 hard-exit combination produces the LARGEST per-loss magnitudes of all 9 rulesets (R2-A 3.29R / D2 2.14R) + the lowest trigger conversion (R2-A 0.38 / D2 0.29). Not competitive on either lever.

I_edwards_magee's lower-trough stop + 1.5x rally-volume gating produces middling magnitudes (closer to G's tight-stop profile than to E's wider profile). I's trigger conversion is the second-lowest. The volume-gating mechanism filters out weaker breakouts but the filtration is NOT compensated by better post-entry survival at the substrate sizes available.

### Finding 4 -- V2-binding-variable cohort selection ENRICHES per-ticker W-pattern productivity but produces SMALL substrates

V2-mechanic Turn H analysis (merge `64e0099`) established that V2 substrates are NOT W-pattern-thin per ticker -- they are 7.2x to 70x ENRICHED vs the bias-free D2 baseline (D_filt 0.138). The "substrate thinness" framing in R2-A + R2-D findings was a function of small substrate SIZE (T<=15 in all 5 V2 cases; baseline T=516), NOT low per-ticker W incidence.

R2-A's NEGATIVE on E + R2-D's INSUFFICIENT SAMPLE reflect substrate-size + survival-quality limitations rather than W-pattern depletion. V2 selection IS methodologically informative; but the actionable trade outcome QUALITY on V2-selected tickers requires substrate-size-aware verdict gating.

### Finding 5 -- The applied research arc has reached methodological end-point at current substrate scale

The cumulative evidence pattern is coherent: no ruleset survives all three discipline gates; the closest near-success failed substrate-freshness reproducibility; per-variable substrates are too small for robust per-ruleset evaluation; the bias-free baseline cohort is not stable across regenerations. Further ruleset variants tested against the same substrate construction methodology would likely reproduce the same pattern.

**The substantive forward question is methodological**: build a substrate construction methodology that eliminates the failure modes. Phase 14 temporal log infrastructure is the operator-approved answer.

---

## Sec 5 Methodological lessons banked

Five cumulative CLAUDE.md gotchas emerged from the arc:

| # | Gotcha | Source arc | BINDING from |
|---|---|---|---|
| **#33** | Cohort-validity-vs-verdict-criteria distinction | D2 Amendment 3 + R2-A reinforcement + R2-D third canonical application | 40th cumulative validation |
| **#34** | Brief-prescription cross-table verification | R2-D Codex R1.M#1 (sp=1 vs sp=2.0 SUMMARY TABLE) | 42nd cumulative validation |
| **#35** | Substrate density metric disambiguation | V2-mechanic Slice 5 implementer triage | 43rd cumulative validation |
| **#36** | Two-Codex-chain default for applied research dispatches | Operator-identified meta-lesson post-V2-mechanic; validated at G2 chain #1 | 44th cumulative validation |
| **#37** | Substrate-freshness sensitivity (cohort fixture membership drift) | G2 Brief Amendment 1 (D2 N=71->N=42) | 45th cumulative validation |

The five gotchas form a cumulative brief-authoring + fixture-management discipline family that applies to ALL future applied research dispatches.

---

## Sec 6 Methodological deliverables (preserved beyond the arc)

Even with NO deployable ruleset finding, the arc produced four methodological deliverables that ARE valuable for Phase 14 and beyond:

1. **9-metric scorecard framework** (G2 brief Sec 1.4; implementation at `research/harness/g2_w_bottom_ruleset_backtest/scorecard.py`) -- expectancy_R + win_rate + avg_win_R + avg_loss_R + profit_factor + trigger_conversion_rate + median_time_in_trade + open_at_tail_count + estimated_dollar_per_period; richer than win-rate-and-mean-R alone; ready for future evaluations against the temporal log

2. **Per-variable 3-axis profile tag taxonomy** (V2-mechanic Brief Amendment 4) -- ENRICHED/TYPICAL/DEPLETED productivity + SUFFICIENT/MARGINAL/INSUFFICIENT substrate size + COMPARABLE/DEGRADED/SUPPRESSED survival rate; descriptive labels per gotcha #33; replaces single-categorical-headline verdicts

3. **Two-Codex-chain default discipline** (gotcha #36) -- chain #1 implementation review BEFORE smoke artifact emission; chain #2 methodology + narrative review AFTER smoke + findings; G2 validated the pattern catches 3C+13M+12m pre-smoke that would otherwise have been caught post-smoke requiring re-runs

4. **Five brief-authoring discipline gotchas (#33-#37)** -- cohort-validity + brief-prescription cross-table + substrate density metric disambiguation + two-Codex-chain default + substrate-freshness sensitivity; collectively the "brief-authoring + fixture-management" discipline family

---

## Sec 7 Future-revisit predicates

The applied research arc may be re-opened when the following conditions are simultaneously met:

1. **Substrate scale**: N >= 100 patterns per substrate (vs current N<=15 V2; N=42-71 D2). Achieved when the Phase 14 temporal log accumulates ~3-6 months of daily observations.

2. **Cohort fixture stability**: frozen regeneration semantics (gotcha #37 eliminated by construction in the temporal log; OR cohort-stability LOCK at fixture-write time deployed for legacy cohort extractors).

3. **At least one ruleset that achieves all three discipline gates simultaneously**: (a) statistical defensibility (CI lower bound positive + N>=10 closed); (b) cohort-validity (no substitution; gotcha #33); (c) substrate-freshness reproducibility (gotcha #26 + #37). NONE of the 9 rulesets tested in the arc met this.

4. **Multi-substrate consistency**: positive expectancy reproduces across at least 2 independent substrates (not just bias-free OR V2-selected; both).

5. **Operator-approved revisit framing**: the question to be re-tested is well-formed + the discipline gates are pre-committed at brief authoring time.

When all 5 predicates are satisfied, a Phase 15+ applied research arc may revisit ruleset deployment. Until then, manual operator-driven trade management continues as the production approach.

---

## Sec 8 How to reference this arc in future work

**Canonical citation form (use in future dispatch briefs, study writeups, return reports, gotchas, and architectural decisions):**

> Per the 2026-05-27 applied research arc closure (`research/studies/2026-05-27-applied-research-arc-closure.md`; commits `a43a921` through `bf7e071`): {specific lesson cited}.

**Common citation use cases:**

- For brief-authoring discipline references: "Per arc closure Sec 5 + cumulative gotchas #33-#37"
- For substrate-thinness vs per-ticker-enrichment framing: "Per arc closure Finding 4 (V2-mechanic Turn H synthesis)"
- For ruleset-deployment-not-justified framing: "Per arc closure Sec 4 Finding 5 + Sec 7 future-revisit predicates"
- For substrate-freshness sensitivity citation: "Per arc closure Finding 1 + gotcha #37"
- For the 9-metric scorecard framework: "Per arc closure Sec 6 #1 (G2 scorecard.py)"

**Memory pointer (banked at this commissioning):**

A memory entry at `C:\Users\rwsmy\.claude\projects\c--Users-rwsmy-swing-trading\memory\project_applied_research_arc_2026-05-27.md` points to this closure document so future orchestrator sessions discover it at conversation start.

**Cross-document pointers:**

- Phase 14 commissioning brief at `docs/phase14-commissioning-brief.md` references this closure document at Sec 1 + Sec 2.5 (temporal log rationale)
- CLAUDE.md gotchas #33-#37 reference this arc's specific failure modes
- phase3e-todo Turn H 2026-05-27 PM #3 entry references this closure as the arc-completion record

**For new orchestrator sessions:** if you encounter applied-research-related work, START by reading this closure document + the linked per-arc findings docs (Sec 2 arc map). Do NOT relitigate the arc's conclusions; the operator-validated synthesis is canonical.

---

## Sec 9 Per-arc artifact pointers

For full forensic detail per arc:

| Arc # | Findings doc | Return report | Smoke artifact | Brief |
|---|---|---|---|---|
| 1 V2 evaluator | `research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md` | `docs/v2-ohlcv-criterion-evaluator-executing-plans-return-report.md` | `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.{csv,md}` | `docs/superpowers/plans/2026-05-23-v2-ohlcv-criterion-evaluator-plan.md` |
| 2 V2 full-reproduction | `docs/v2-full-reproduction-drift-investigation-2026-05-24.md` | (no return report; investigation) | (uses same V2 sensitivity smoke) | (no brief; investigation) |
| 3 D1 backtest | `docs/d1-tightness-1005-backtest-findings-2026-05-25.md` (path approximation) | `docs/d1-tightness-1005-backtest-return-report.md` (path approximation) | `exports/research/w-bottom-ruleset-comparison-20260525T*` | `docs/d1-tightness-1005-backtest-dispatch-brief.md` |
| 4 D2 6-ruleset + Amendment 5 | `docs/pattern-cohort-w-bottom-ruleset-comparison-findings-2026-05-25.md` | (return report path approximation) | `exports/research/w-bottom-ruleset-comparison-20260525T210703Z/` (EXPANDED smoke) | (D2 dispatch brief path approximation) |
| 5 R2-A | `docs/r2a-tightness-days-required-cohort-backtest-findings-20260526.md` | `docs/r2a-tightness-days-required-cohort-backtest-return-report.md` | `exports/research/w-bottom-ruleset-comparison-20260525T224203Z/` | `docs/r2a-vcp-tightness-days-required-cohort-backtest-dispatch-brief.md` |
| 6 R2-D | `docs/r2d-adr-min-pct-cohort-backtest-findings-20260526.md` | `docs/r2d-adr-min-pct-cohort-backtest-return-report.md` | `exports/research/w-bottom-ruleset-comparison-20260526T062529Z/` | `docs/r2d-adr-min-pct-cohort-backtest-dispatch-brief.md` |
| 7 V2-mechanic | `docs/v2-selection-mechanic-analysis-findings-2026-05-26.md` + `research/studies/2026-05-26-v2-selection-mechanic-analysis.md` (study writeup) | `docs/v2-selection-mechanic-analysis-return-report.md` | `exports/research/v2-selection-mechanic-analysis-20260527T084319Z/` | `docs/v2-selection-mechanic-investigation-dispatch-brief.md` |
| 8 G2 | `docs/g2-w-bottom-ruleset-backtest-findings-20260527.md` | `docs/g2-w-bottom-ruleset-backtest-return-report.md` | `exports/research/g2-w-bottom-ruleset-backtest-20260527T213434Z/` | `docs/g2-w-bottom-ruleset-backtest-dispatch-brief.md` (with Orchestrator Amendment 0 + Brief Amendments 1-4) |

Some path approximations should be verified via `git log --diff-filter=A -- docs/*.md` for the dates in question if forensic precision is needed.

---

*End of applied research arc closure document. The arc tested 9 named rulesets across 4 substrates from 2026-05-23 through 2026-05-27; established that NO tested ruleset produces robust positive expectancy at current substrate scale; surfaced 5 methodological discipline gotchas (#33-#37); produced the 9-metric scorecard framework + per-variable 3-axis profile tag taxonomy + two-Codex-chain Codex MCP discipline; closed with the operator-validated synthesis that ruleset deployment is not justified by arc evidence. The forward path is Phase 14 temporal pattern detection + observation log infrastructure (commissioned 2026-05-27 PM #3 at `bf7e071`). Citation form: "per the 2026-05-27 applied research arc closure".*
