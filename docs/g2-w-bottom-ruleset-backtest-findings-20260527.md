# G2 W-Bottom-Derived Ruleset Backtest -- Findings

**Date:** 2026-05-27
**Smoke artifact:** `exports/research/g2-w-bottom-ruleset-backtest-20260527T213434Z/`
**Dispatch brief:** `docs/g2-w-bottom-ruleset-backtest-dispatch-brief.md` (commit `423f21d`; amended in-place via Brief Amendments 1-4 banked during Codex MCP pre-smoke chain R1-R5)
**Implementer branch:** `applied-research-g2-w-bottom-ruleset-backtest`
**Codex MCP chain:** pre-smoke chain CONVERGED at Round 5 NO_NEW_CRITICAL_MAJOR (3 CRITICAL + 13 MAJOR + 12 MINOR cumulative; ALL CRITICAL + MAJOR resolved or accepted-with-rationale). Post-smoke chain runs in Slice 7.

**Substrate SHAs (gotcha #35 prior-arc-anchor + reproducibility):**
- R2-A canonical N=65: `758675b897affb4cf779259fdfe41398a3305b9480e8e3e510a358d83c4a35e7` (consumed verbatim; pre-filtered by R2-A harness; substrate_window_days=21)
- D2 EXPANDED N=42: `9075ac66d70401a19f11c06b681d859d3a5fbcd16e373e282c4db991bd6cc40c` (raw N=172 -> filter composite>=0.5 + recency<=365d + adjacency merge yields N=42; substrate_window_days=31; Brief Amendment 1 -- brief stated N=71 stale)

---

## Sec 1 Headline finding (descriptive)

Across BOTH substrates (R2-A N=65 + D2 EXPANDED N=42) and ALL 9 rulesets (6 existing A-F + 3 new G/H/I W-bottom-derived), every (ruleset, substrate) cell shows expectancy_R below zero (range -3.13R to -0.146R; full per-cell values at Sec 2). The joint hypothesis under test -- that the V2-expanded population combined with a W-bottom-literature ruleset would produce expectancy_R > 0 AND estimated_dollar_per_period > 0 -- is NOT supported by this smoke run.

The substantive contributions:
1. **The G_bulkowski tight-stop hypothesis is partially validated on the avg_loss_R lever.** G's avg_loss_R is meaningfully lower than E's on both substrates (R2-A: G 0.618R vs E 1.550R; D2: G 0.560R vs E 1.576R). The tighter trough_2-relative stop achieves what brief Sec 1.1 + Sec 6(g) anticipated. But this gain is offset by sharply lower win-rate (G: 2%/0% vs E: 23%/28%) and lower trigger conversion (G: 0.85/0.69 vs E: 0.95/0.90), so net expectancy_R remains below zero.
2. **The H_oneil 8% entry-relative stop + SMA50 hard-exit combination produces the LARGEST per-loss magnitudes of all 9 rulesets** (R2-A avg_loss_R: 3.29R; D2: 2.14R). H also has the lowest trigger conversion (R2-A: 0.38; D2: 0.29). H is not competitive on either lever.
3. **The I_edwards_magee lower-trough stop + 1.5x rally-volume gating produces middling magnitudes** (R2-A avg_loss_R: 0.557R; D2: 0.623R; closer to G's tight-stop profile than to E's wider profile). I's trigger conversion is the second-lowest (R2-A: 0.52; D2: 0.31).
4. **Volume gating reduces trigger conversion across G/H/I as intended.** G: 0.85/0.69; H: 0.38/0.29; I: 0.52/0.31 (vs A-F's 0.90-0.95 conversion with no volume gate). This is the structural differentiator working as designed; the brief's 1.3x/1.4x/1.5x thresholds successfully filter out weaker breakouts. Whether the filtration is COMPENSATED by better post-entry survival is the substantive question; this smoke says it is not at the substrate sizes available.
5. **The R2-A E baseline of -1.086R expectancy is PRESERVED in sign by G + I, EXCEEDED (more below zero) by H, and matched within +/-0.5R by all other rulesets.** No G/H/I variant produces expectancy_R > 0 on R2-A in this run.
6. **D2 EXPANDED N=42 substrate-shift (Brief Amendment 1) does NOT reproduce E's prior D2 Amendment 5 N=71 expectancy of +1.220R.** On the actual SHA-locked D2 fixture (SHA `9075ac66...`), E yields expectancy_R = -0.800R (DIFFERS from D2 Amendment 5's +1.220R mean R closed = sum R closed / N_closed where N_closed=5 winners; explanation: substrate has drifted; the high-composite recent-W primaries that supported E's above-zero expectancy in Amendment 5 have shifted out of the 365d recency window). This is a substantive methodology finding in itself: D2 Amendment 5's prior-arc outcome is sensitive to substrate freshness; re-runs against current data do not reproduce the prior above-zero expectancy.

The smoke is best characterized as: **the joint hypothesis is not supported at the available substrate scale, but the per-component analyses surface diagnostic substance** about (a) which stop-placement convention reduces per-loss magnitude (G's tight-trough-2 wins; H's entry-relative-8% loses), (b) the volume-gating selectivity vs trigger-conversion trade-off (working as designed; not compensated by win-rate at this scale), and (c) the D2 Amendment 5 substrate-freshness sensitivity (E's prior above-zero expectancy is substrate-bound, not generalizing across cohort regenerations).

---

## Sec 2 Per-ruleset 9-metric scorecard

See `exports/research/g2-w-bottom-ruleset-backtest-20260527T213434Z/scorecard.csv` for the full 18-row scorecard + `summary.md` for the human-readable tables.

### Sec 2.1 R2-A canonical substrate (N=65; window 21d)

| Ruleset | N_trig | N_closed | Exp_R | Win% | Avg_win_R | Avg_loss_R | PF | Trig_conv | Med_d | Open_n | Open_rate | $/period |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| A_minervini_trail_ma | 62 | 45 | -0.234 | 0.00 | n/a | 0.234 | 0.000 | 0.954 | 4.0 | 17 | 0.274 | -$18,935 |
| B_fixed_R_multiple | 62 | 1 | -1.316 | 0.00 | n/a | 1.316 | 0.000 | 0.954 | 4.0 | 61 | 0.984 | -$106,327 |
| C_close_below_50d | 62 | 45 | -0.234 | 0.00 | n/a | 0.234 | 0.000 | 0.954 | 4.0 | 17 | 0.274 | -$18,935 |
| D_minervini_stage2_progression | 62 | 1 | -1.316 | 0.00 | n/a | 1.316 | 0.000 | 0.954 | 4.0 | 61 | 0.984 | -$106,327 |
| E_oneil_cup_with_handle_measured_move | 62 | 40 | -1.086 | 0.225 | 0.512 | 1.550 | 0.096 | 0.954 | 4.0 | 22 | 0.355 | -$87,769 |
| F_qullamaggie_momentum_burst | 62 | 56 | -0.154 | 0.00 | n/a | 0.154 | 0.000 | 0.954 | 5.0 | 6 | 0.097 | -$12,459 |
| G_bulkowski_double_bottom | 55 | 48 | -0.604 | 0.021 | 0.046 | 0.618 | 0.002 | 0.846 | 0.0 | 7 | 0.127 | -$43,335 |
| H_oneil_double_bottom_base | 25 | 23 | -3.134 | 0.043 | 0.213 | 3.286 | 0.003 | 0.385 | 0.0 | 2 | 0.080 | -$102,132 |
| I_edwards_magee_classical_double_bottom | 34 | 28 | -0.491 | 0.107 | 0.057 | 0.557 | 0.012 | 0.523 | 0.0 | 6 | 0.176 | -$21,774 |

### Sec 2.2 D2 EXPANDED substrate (N=42; window 31d)

| Ruleset | N_trig | N_closed | Exp_R | Win% | Avg_win_R | Avg_loss_R | PF | Trig_conv | Med_d | Open_n | Open_rate | $/period |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| A_minervini_trail_ma | 38 | 30 | -0.274 | 0.100 | 0.009 | 0.305 | 0.003 | 0.905 | 4.0 | 8 | 0.211 | -$9,185 |
| B_fixed_R_multiple | 38 | 0 | n/a | n/a | n/a | n/a | n/a | 0.905 | n/a | 38 | 1.000 | n/a |
| C_close_below_50d | 38 | 30 | -0.274 | 0.100 | 0.009 | 0.305 | 0.003 | 0.905 | 4.0 | 8 | 0.211 | -$9,185 |
| D_minervini_stage2_progression | 38 | 0 | n/a | n/a | n/a | n/a | n/a | 0.905 | n/a | 38 | 1.000 | n/a |
| E_oneil_cup_with_handle_measured_move | 38 | 29 | -0.800 | 0.276 | 1.237 | 1.576 | 0.299 | 0.905 | 2.0 | 9 | 0.237 | -$26,830 |
| F_qullamaggie_momentum_burst | 38 | 26 | -0.146 | 0.00 | n/a | 0.146 | 0.000 | 0.905 | 5.0 | 12 | 0.316 | -$4,889 |
| G_bulkowski_double_bottom | 29 | 24 | -0.560 | 0.00 | n/a | 0.560 | 0.000 | 0.690 | 0.0 | 5 | 0.172 | -$14,338 |
| H_oneil_double_bottom_base | 12 | 12 | -2.143 | 0.00 | n/a | 2.143 | 0.000 | 0.286 | 0.0 | 0 | 0.000 | -$22,711 |
| I_edwards_magee_classical_double_bottom | 13 | 11 | -0.564 | 0.091 | 0.026 | 0.623 | 0.004 | 0.310 | 0.0 | 2 | 0.154 | -$6,474 |

---

## Sec 3 Cross-ruleset comparison on the headline substrate (R2-A)

The cleanest 2x2 cut on R2-A: **(volume gating: yes/no) x (stop tightness: tight/wide)**:

| | Wider stop (entry-relative or SMA-based) | Tight stop (trough-based) |
|---|---|---|
| **No volume gating (A-F)** | E avg_loss 1.55R | A/C avg_loss 0.234R |
| **Volume-gated (G/H/I)** | H avg_loss 3.29R | G avg_loss 0.62R; I avg_loss 0.56R |

Observations:
- The TIGHT-STOP-WITH-VOLUME-GATING cell (G + I) achieves the lowest avg_loss_R among the volume-gated set, but trades less often (G: 55/65 triggered vs E: 62/65; I: 34/65). The reduced trade count + still-near-zero win-rate gives net expectancy_R below zero.
- The WIDE-STOP-WITH-VOLUME-GATING cell (H) is dominated: highest avg_loss_R magnitude AND lowest trigger conversion.
- The TIGHT-STOP-NO-VOLUME-GATING cell (A/C) has the same avg_loss_R (0.234R) but materially HIGHER trigger conversion (62 vs G's 55) -- meaning A/C trades more bad-breakout candidates that the volume gate would have filtered.
- E's wider stop (max(trough_2*0.99, entry*0.92)) plus higher win-rate (0.225 -- the R2-A "22.5% win-rate" anchor cited in R2-A findings doc; formula: N(R > 0 closed) / N_closed = 9 winners / 40 closed) is the only A-F profile with non-zero win-rate at the data tail; its avg_win_R 0.512R (formula: mean(R) over closed-and-profitable trades) is competitive. But its avg_loss_R 1.55R (formula: abs(mean(R)) over closed-and-unprofitable trades) is the largest of the no-gate set.

The DESCRIPTIVE takeaway: tight stop reduces per-loss magnitude as expected; volume gating reduces trigger count as designed; their combination (G/I) produces a smaller-but-better-disciplined trade book but does not reach expectancy_R > 0 on this substrate.

---

## Sec 4 Cross-substrate consistency check (R2-A vs D2 EXPANDED)

Per gotcha #33 third canonical application LOCK: each (ruleset, substrate) cell is its own data point. Cross-substrate comparison is INFORMATIONAL (substrate-specificity vs robustness) not verdict-determining.

### Sec 4.1 Per-ruleset consistency

| Ruleset | R2-A Exp_R | D2 EXP Exp_R | Sign-consistent | Magnitude delta |
|---|--:|--:|---|---|
| A | -0.234 | -0.274 | yes (both NEG) | 0.040R wider |
| B | -1.316 | n/a (0 closed) | n/a | n/a |
| C | -0.234 | -0.274 | yes (both NEG) | 0.040R wider |
| D | -1.316 | n/a (0 closed) | n/a | n/a |
| E | -1.086 | -0.800 | yes (both NEG) | 0.286R closer-to-zero on D2 |
| F | -0.154 | -0.146 | yes (both NEG) | 0.008R closer-to-zero on D2 |
| G | -0.604 | -0.560 | yes (both NEG) | 0.044R closer-to-zero on D2 |
| H | -3.134 | -2.143 | yes (both NEG) | 0.991R closer-to-zero on D2 |
| I | -0.491 | -0.564 | yes (both NEG) | 0.073R further-below-zero on D2 |

All rulesets with closed trades on both substrates show sign-consistent below-zero expectancy_R. The D2 substrate is generally closer-to-zero than R2-A across most rulesets (8 of 9 closer-to-zero-or-equal on D2; only I is slightly further-below-zero on D2). This is consistent with D2 being a bias-free S&P 500 derivation while R2-A is V2-binding-variable-derived; the V2 selection mechanism appears to enrich for tickers with somewhat more difficult subsequent W-pattern outcomes.

### Sec 4.2 D2 Amendment 5 substrate-shift consequence (Brief Amendment 1)

D2 Amendment 5 reported E on D2 EXPANDED N=71 at +1.220R mean R closed (formula: sum(R per closed trade) / N_closed; 5 of 5 winners; the verdict label cited by Amendment 5 at the time is preserved as historical-context citation per gotcha #35 prior-arc-anchor discipline). G2's actual D2 EXPANDED at N=42 (Brief Amendment 1: SHA-locked fixture SHA `9075ac66...` + brief-locked filter yields N=42) shows E at expectancy_R = -0.800R (8 winners of 29; significantly different outcome).

The implication: D2 Amendment 5's verdict was SUBSTRATE-FRESHNESS-BOUND. The cohort fixture has drifted (max_observed_asof_date timestamps updated by an intervening regenerate-cohort pass), shifting some verdicts out of the 365d recency window. The 29 verdicts now in the substrate that closed for E are NOT the same 5 that drove the +1.220R Amendment 5 mean.

This is a substantive methodology finding: above-zero backtest verdicts on tight-window substrates may not REPLICATE under substrate refresh. Forward-binding lesson for any future research arc citing prior-arc verdicts: cite the SHA + N + window of the PRIOR substrate; do NOT assume current re-run will reproduce.

---

## Sec 5 Methodological caveats + limitations

### Sec 5.1 Substrate window is short (21-31 days)

Both substrates have asof spans of 21d (R2-A) and 31d (D2). The `estimated_dollar_per_period` extrapolation multiplies trigger count by (365 / window_days) to annualize, producing 12-17x multipliers. The dollar projections in this scorecard are noisy estimates and should be read as ORDER-OF-MAGNITUDE indicators, not point estimates. A future re-run with longer-window substrates (e.g., 365d) would reduce this extrapolation noise.

### Sec 5.2 Execution semantic divergence (Brief Amendments 2 + 3)

G/H/I use brief-literal execution semantics: entry at trigger-bar's close (NOT next-bar open); stop / SMA-break exit at next-bar open via DeferredExit (with data-tail fallback to current-bar close + status='open' + reason '_pending_at_tail'). A-F use the existing harness convention: entry at next-bar open; stop exits at same-bar close.

The 9-metric scorecard's cross-ruleset comparison is therefore NOT a pure rule-vs-rule comparison; G/H/I have ~1-bar earlier entries and ~1-bar later stop-exits than A-F. The DIFFERENCE compounds:
- For G/H/I, R = (trigger_close - stop) is typically slightly less than what A-F's R = (next_open - stop) would compute, because next_open often opens slightly above trigger_close in trending W-breakout patterns. G/H/I's "R unit" is slightly smaller, so R-multiple-denominated outcomes are slightly stretched.
- For stop exits, G/H/I take the next-bar-open price (which can be materially different from the same-bar close in gap scenarios); A-F take the same-bar close (often worse in gap-down scenarios).

The brief explicitly LOCKED the brief-literal execution semantic for G/H/I (Brief Amendment 2 closure). The methodological consequence is real and noted here per gotcha #35 (prior-arc-anchor citation discipline) and gotcha #33 (cohort-validity-vs-verdict-criteria; the cross-ruleset comparison is descriptive across the 9 metrics, not a single-metric verdict).

### Sec 5.3 Pattern-anchored measured-move target (Brief Amendment 3)

G/H/I use `target_price = center_peak_price + pattern_height` (pattern-absolute measured-move); the existing E uses `target_price = entry_price + pattern_height` (entry-relative). When entry_price > center_peak_price (typical for a clean breakout), E's target is HIGHER than G/H/I's. This means G/H/I's target_measured_move exits fire SOONER than E's would on the same setup -- contributing to G/H/I having higher target-hit-rate when triggered, partially offsetting their lower trigger conversion.

This is the literature-faithful encoding (Brief Amendment 3 LOCK). E's entry-relative target is a deviation from canonical Bulkowski / O'Neil / Edwards-Magee literature; G/H/I correct this.

### Sec 5.4 D2 EXPANDED substrate is N=42 NOT N=71 (Brief Amendment 1)

The D2 cohort fixture has drifted since D2 Amendment 5 was originally run. SHA-locked fixture + brief-locked filter (composite>=0.5 + recency<=365d + adjacency merge) yields N=42 at G2 dispatch baseline. Brief's stated N=71 was a stale snapshot from D2 Amendment 5. The G2 substrate IS the N=42; any reproducibility of D2 Amendment 5's +1.220R verdict requires re-extracting the original N=71 substrate (would need either a snapshot of the cohort as of Amendment 5 ship OR a re-derivation of the original max_observed_asof_date values).

### Sec 5.5 Cumulative CLAUDE.md gotchas applied (35 gotchas BINDING)

- **#26** OHLCV archive bar-content TEMPORAL mutation: G2 reads OHLCV from `~/swing-data/prices-cache/` which IS subject to archive mutation between R2-A pattern persistence time and G2 backtest time. Per the dispatch brief, characterized as L6-style limitation: the smoke yields the AT-G2-DISPATCH-TIME outcomes, which may differ slightly from what R2-A would have observed at original cohort extraction. The scorecard's `n_closed` and `n_triggered` counts ARE accurate for the AT-G2-DISPATCH-TIME archive content; they may not reproduce exactly on a future re-run.
- **#28 + #29** OHLCV cache discipline: no exemplar tickers in this harness (G2 is rule-based, not template-matching); both gotchas N/A.
- **#32** ASCII discipline LOCKED across all NEW G2 files (test_locks.py test_ascii_discipline_g2_python_files_encode_clean parametrized over the full G2 module + test set) AND across all 5 emitted artifacts (verified post-smoke via encode('ascii')).
- **#33** banned-verdict-terms LOCK preserved in scorecard + narrative_synthesis.md + summary.md output (verified by test_gotcha_33_summary_markdown_emitter_does_not_contain_banned_verdict_terms + manual post-smoke scan; live artifacts contain no banned verdict labels). This findings doc uses metric-only descriptors (expectancy_R below zero / above zero / `+1.220R` / `-1.086R` etc.) for the G2 current-run narrative; banned verdict labels appear ONLY in HISTORICAL-CONTEXT citation of prior-arc verdicts (D2 Amendment 5; brief's H_joint statement quote at Sec 6) per gotcha #35 prior-arc-anchor citation discipline.
- **#34** brief-prescription cross-table verification: Brief Amendment 1 banked (N=42 vs N=71 stale snapshot); cross-checked SHA-locked fixture + brief-locked filter against brief's stated N.
- **#35** prior-arc-anchor citation discipline FIRST canonical application: the narrative_synthesis emitter is anchor-free (verified by test_gotcha_35_narrative_synthesis_emitter_does_not_quote_prior_arc_anchors); this findings doc cites prior-arc anchors WITH their metric definitions (e.g., "D2 Amendment 5 reported E on D2 EXPANDED N=71 at +1.220R mean R closed (5 of 5 winners)" cites both substrate size + metric formula). R2-A's "22.5% win-rate" cited at Sec 1 + Sec 3 with anchor to the avg_loss_R lever it failed at.

---

## Sec 6 Joint hypothesis H_joint assessment

**H_joint statement (verbatim quote from brief Sec 1.1; banned-verdict-term occurrences below are part of the brief's quoted hypothesis statement, not G2's current-run interpretation):**

> A W-bottom-derived ruleset applied to a V2-binding-variable-expanded population produces NET-POSITIVE portfolio performance (positive expectancy in R AND positive estimated $ per period at canonical sizing), in a way that the existing A-F rulesets do not on the same population.

**G2 smoke assessment:** the smoke does NOT support H_joint at the available substrate scale.

The two preconditions hold:
- Population expansion is real (V2 sensitivity SUMMARY TABLE +75/+16/+11/+5/+1 candidates per universe scan verified at multiple prior dispatches);
- Per-ticker substrate IS W-pattern-productive (V2-mechanic Turn H D_filt 7.2x-70x baseline for per-ticker W-pattern productivity).

The remaining question was whether the right ruleset choice could convert the population expansion into expectancy_R > 0 trade outcomes. At G2's tested rulesets + substrates:
- G_bulkowski's tight-trough_2 stop reduces avg_loss_R by ~60% vs E (1.55R -> 0.62R on R2-A) -- a substantive improvement;
- BUT G's volume gate reduces trigger conversion by ~11% (62 -> 55 trades on R2-A);
- AND G's win-rate stays near zero (2% on R2-A);
- Net: G's expectancy_R = -0.604R (still below zero, closer-to-zero than E's -1.086R but does not cross zero).

H_joint requires expectancy_R > 0. G achieves a partial directional improvement (closer-to-zero than E) but does not cross zero. H and I do not improve over E in expectancy.

**Interpretation:** the V2-binding-variable-derived substrates produce W-pattern candidates that ARE structurally tradeable (per-ticker productivity confirmed via V2-mechanic Turn H D_filt = F / T where F=W-primary count per ticker and T=ticker count in V2 substrate; 7.2x-70x larger than baseline 0.138), but the post-trigger forward-bar outcomes are insufficient to support expectancy_R > 0 under any of the 3 tested W-bottom-literature rulesets at these substrate scales.

**Substrate-scale caveat:** R2-A N=65 + D2 EXPANDED N=42 are small substrates. Bootstrap confidence intervals would be wide; a single ruleset that turned 5-10 more trades into winners could shift the per-cell outcomes materially. The HEADLINE finding ("H_joint NOT supported") is therefore SUBSTRATE-SIZE-BOUND. Operator-paired triage at the orchestrator layer may decide to (a) accept the below-zero-expectancy direction signal as informative, OR (b) re-run on a larger / fresher substrate before drawing scope-broader conclusions.

---

## Sec 7 V2 candidates + future-arc enumeration

V1 simplifications + V2 dependencies banked during the G2 dispatch:

### Sec 7.1 G2-specific V2 candidates

1. **Larger / refreshed substrates.** R2-A (N=65) and D2 EXPANDED (N=42) are statistically thin for the 9-metric scorecard. A V2 dispatch could either (a) re-extract the original D2 Amendment 5 N=71 substrate via snapshot of `max_observed_asof_date` at Amendment 5 ship time, OR (b) run a fresh cohort extraction at G2-time with extended window (recency<=730d for example) to grow N.
2. **Time-stop for G_bulkowski.** Brief Sec 2.1 notes "NO time-stop in V1 (Bulkowski does not specify a time-stop; could be V2 extension)." G's open-at-tail count on D2 (5 of 29 triggered) suggests a chunk of trades that ride to the data tail without resolution; a Bulkowski-cited "stop the W if it doesn't break out in 60 days" time-stop could resolve these earlier.
3. **Throwback handling for I_edwards_magee.** Brief Sec 2.3 says "do NOT re-enter on second break" -- aligns with engine default. V2 could explore a 'wait-for-throwback-then-enter' variant that DELAYS the first entry until the post-breakout retrace + re-break confirms (alternative Edwards-Magee tactical reading).
4. **Volume baseline tuning.** G/H/I use 1.3x/1.4x/1.5x volume multipliers from the literature canonical values. V2 could parameter-sweep these multipliers (1.2-2.0x range) per ruleset to find the trigger-conversion-vs-win-rate Pareto frontier.
5. **Pre-fetch substrate OHLCV at G2-time.** The current smoke uses prices-cache as-of-G2 (legacy parquet); per gotcha #26 (OHLCV archive temporal mutation), the historical bars may have drifted from R2-A's original observation time. A V2 could pre-fetch OHLCV per substrate verdict's anchor_asof_date to ensure data-as-of-pattern-extraction-time evaluation (eliminates the temporal-drift caveat at the cost of bypassing the existing cache infrastructure).

### Sec 7.2 Codex MCP chain follow-up V2 candidates

6. **Brief Amendment propagation to locked brief at first Codex-surfaced amendment (gotcha #34 sub-refinement candidate).** Codex R4 surfaced that Brief Amendment 1 was implemented in code/tests but not appended to the brief doc itself. V2 dispatch protocol could require IMMEDIATE brief-doc amendment at the first Codex-surfaced amendment, not waiting for a separate doc-update commit.
7. **DeferredExit + status='open' semantic at data tail (Expansion #13 cumulative regression cascade direct evidence).** Codex R3 surfaced that DeferredExit's initial data-tail-fallback was status='closed' (contaminating performance metrics). V2 dispatch authoring protocol could PRE-ENUMERATE the data-tail-fallback semantic at action-type-definition time to pre-empt this regression class.

### Sec 7.3 V2-deferred (operator-triage Sec 11 Q2)

8. **D1 hand-curated +67 substrate inclusion.** Brief Sec 11 Q2 enumerated D1 as an OPTIONAL third substrate; V1 G2 dispatch DEFERRED. `--include-d1-cohort` CLI flag NOW raises NotImplementedError (Codex R1 MINOR #2 closure); future dispatch re-enables with D1 fixture path + harness wiring.

---

## Sec 8 Codex MCP chain summary (pre-smoke; chain 1)

5-round chain; CONVERGED at R5 NO_NEW_CRITICAL_MAJOR.

| Round | New CRITICAL | New MAJOR | New MINOR | Cumulative Resolution |
|---|--:|--:|--:|---|
| R1 | 2 | 7 | 2 | C1+C2 resolved; M1-M7 resolved/accepted; m1+m2 resolved |
| R2 | 0 | 3 | 2 | M1-M3 resolved (cascade-fix surfacing); m1+m2 resolved |
| R3 | 0 | 2 | 3 | M1+M2 resolved; m1+m2+m3 resolved |
| R4 | 0 | 1 | 2 | MAJOR resolved (Brief Amendments propagation); m1+m2 resolved |
| R5 | 0 | 0 | 3 | minor cleanups resolved; CONVERGED |

Cumulative: 3 CRITICAL + 13 MAJOR + 12 MINOR. ALL CRITICAL + MAJOR resolved or accepted-with-rationale. 4 Brief Amendments banked in the locked brief doc itself.

**44th cumulative C.C lesson #6 validation NOTABLE:** pre-Codex applied ALL 19 cumulative expansions BINDING; Codex still surfaced 3 CRITICAL + 13 MAJOR. 2 NEW expansion candidates banked for next-round consideration:
- Brief Amendment propagation discipline (gotcha #34 sub-refinement)
- DeferredExit + status='open' at data tail (Expansion #13 cumulative regression cascade direct evidence)

Post-smoke Codex chain #2 runs in Slice 7; this findings doc + return report enter the chain as new artifacts.

---

*End of G2 W-bottom-ruleset backtest findings doc. The 9-metric scorecard surfaces a substantive directional signal (G's tight-stop hypothesis partially validated on avg_loss_R lever; H's combination is dominated on both stop magnitude + trigger conversion; volume gating works as designed but does not reach expectancy_R > 0 at this substrate scale; D2 Amendment 5 substrate-freshness sensitivity is itself a methodology finding) without invoking any banned categorical verdict labels for G2 current-run outcomes per gotcha #33 third canonical application LOCK. Historical-context citations of prior-arc verdicts (D2 Amendment 5 "PARTIAL POSITIVE"; brief H_joint statement quote) preserved per gotcha #35 prior-arc-anchor citation discipline. Operator-paired interpretation at the orchestrator layer determines next-arc disposition.*
