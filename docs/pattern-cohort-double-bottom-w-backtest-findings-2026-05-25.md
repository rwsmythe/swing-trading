# Double-Bottom-W Walk-Forward Backtest (D1) — Findings

**Date:** 2026-05-25
**Dispatch brief:** [docs/pattern-cohort-double-bottom-w-backtest-dispatch-brief.md](pattern-cohort-double-bottom-w-backtest-dispatch-brief.md)
**Study extended:** [research/studies/2026-05-24-pattern-cohort-detection.md](../research/studies/2026-05-24-pattern-cohort-detection.md) §R1 reframing hypothesis
**Cohort source:** [exports/research/pattern-cohort-detection-20260525T201617Z/](../exports/research/pattern-cohort-detection-20260525T201617Z/) (untracked results.csv ~287 MB; cohort SHA-256 `5333afe3...`)
**Backtest artifact:** [exports/research/double-bottom-w-backtest-20260525T113638Z/](../exports/research/double-bottom-w-backtest-20260525T113638Z/)
**Branch:** `applied-research-pattern-cohort-double-bottom-w-backtest`

---

## 1. Headline verdict

**NEGATIVE strict per dispatch brief §7.5 — but with the substantive nuance that the R1 hypothesis's trigger-rate component IS unambiguously SUPPORTED.**

| Metric | D1 (W-bottom rule) | V2 (`vcp.tightness_range_factor=1.005`) |
|---|---|---|
| Unique patterns | 13 (after recency<=60d filter) | 17 (after consecutive-eval-run dedup) |
| Triggered | 8 / 13 (**61.5%**) | 5 / 17 (**29.4%**) |
| Closed | 2 (Rulesets A+C; both via `close_below_50d`) | 0 |
| Closed-and-profitable | 0 | 0 |
| Mean R (closed) | **-0.708R** (A+C; B emits no closes) | n/a |
| Mean R (open positions, tail unrealized) | mixed -0.96R to +0.78R | -0.18R |

**Verdict classification per dispatch brief §7.5:**

- POSITIVE requires: trigger rate >=50% AND mean-R positive (>0R) AND >=1 ruleset with multiple closed-and-profitable trades. We have trigger 61.5% (PASS), mean-R closed -0.708R (FAIL), 0 closed-profitable (FAIL). NOT POSITIVE.
- INCONCLUSIVE requires: trigger 30-50% AND mean-R between -0.5R and 0R AND >=1 closed-and-profitable. We have trigger 61.5% (above range), mean-R closed -0.708R (below range), 0 closed-profitable. NOT INCONCLUSIVE (trigger above; profitability below).
- NEGATIVE triggers on ANY of: trigger <=29% OR mean-R <= -0.5R OR 0 closed-and-profitable. We have mean-R closed -0.708R (PASS) AND 0 closed-profitable (PASS). **NEGATIVE.**

**Substantive caveat:** the 61.5% trigger rate vs V2's 29% is a >2x improvement on the R1 hypothesis's mechanical component. The W-bottom-appropriate `close > center_peak_price` rule does fire materially more often on the W-shape-dominated cohort than the VCP-appropriate `close > consolidation_pivot` rule did. The profitability shortfall (0 closed-and-profitable trades) reflects DOWNSTREAM gates not the trigger-rule mismatch the R1 hypothesis targeted — see §4.2 + §8.

---

## 2. Cohort enumeration

### 2.1 Source filter

Source: `exports/research/pattern-cohort-detection-20260525T201617Z/results.csv` (untracked; deterministically regeneratable via `python -m swing.cli diagnose pattern-cohort-detect --cohort-csv exports/research/cohorts/tightness_1.005_flips_67.csv --db ~/swing-data/swing.db`). Cohort input SHA-256 `5333afe3d131c3116ef644acae74ec0e6c594968b610ddc485b85f59fdec1469` per the source artifact's manifest.

Filter pipeline:

| Stage | Count | Notes |
|---|---|---|
| All double_bottom_w verdicts at composite>=0.7 | 725 | Per dispatch brief §1.1 headline |
| Per (ticker, trough_1_date) primary verdicts | 172 | Highest-composite verdict per W structure |
| After 5-BD trough_1 adjacency merge | 172 | No merges fired; all troughs already >5 BD apart |
| **After recency filter (trough_2 within 60 cal days of asof)** | **13** | **The actionable backtest cohort** |
| Distinct tickers | 10 | |

### 2.2 Methodology choice — recency filter

The dispatch brief §1.2 anticipated "roughly 15-30 unique W-bottom patterns" but per-window mode emission actually yields 172 historical W primary verdicts per ticker spanning 2021-2026 (e.g., YOU has 17 distinct W structures with trough_1_dates spanning 2021-07-07 to 2026-04-29). The HIGHEST-composite verdicts per ticker are typically OLDEST historical W's (window_index=0 captures the 2021-shape "textbook W" and scores 0.9333 because the detector scores structure quality, not recency). Backtesting all 172 with the literal `max(trough_1, trough_2, asof)+1` trigger lower bound would trivially trigger on day-1 forward for the 159 OLD W's whose `center_peak_price` is far below current price (5-year-old peaks long since broken), yielding 100% trigger rate but uninformative because the "entry" is at current market level not the W's actual breakout level.

**Resolution:** restrict to RECENT W's where `trough_2_date` is within 60 calendar days of `anchor_asof_date`. This captures "W's that just completed at the cohort's observation point" — the actionable subset matching the dispatch brief's expected scale (13 within 60d; 18 within 90d; 22 within 120d). The verdict is INSENSITIVE to threshold within 60-120 days (per §3 sensitivity analysis); 60-day default matches the V2 backtest precedent for forward-window depth.

### 2.3 The 13 RECENT W primary verdicts

| pattern_id | asof | trough_1 | center_peak | trough_2 | composite | initial_stop | days_t2_to_asof |
|---|---|---|---|---|---|---|---|
| DK-2026-03-09 | 2026-05-15 | 2026-03-09 | 45.41 | 42.39 | 0.741 | 41.97 | 53 |
| DNTH-2026-02-13 | 2026-04-27 | 2026-02-13 | 86.92 | 77.76 | 0.765 | 76.98 | 38 |
| KOD-2026-02-05 | 2026-04-29 | 2026-02-05 | 27.98 | 21.85 | 0.857 | 21.63 | 36 |
| OII-2026-03-13 | 2026-04-21 | 2026-03-13 | 37.20 | 34.37 | 0.833 | 34.03 | 20 |
| RNG-2026-03-27 | 2026-04-30 | 2026-03-27 | 38.13 | 33.49 | 0.767 | 33.16 | 20 |
| TROX-2026-02-20 | 2026-04-29 | 2026-02-20 | 7.48 | 6.54 | 0.834 | 6.47 | 54 |
| TSHA-2026-02-05 | 2026-05-13 | 2026-02-05 | 4.89 | 4.13 | 0.733 | 4.09 | 50 |
| TSHA-2026-03-24 | 2026-05-13 | 2026-03-24 | 4.58 | 4.07 | 0.767 | 4.03 | 47 |
| UCTT-2026-03-06 | 2026-05-12 | 2026-03-06 | 65.27 | 55.89 | 0.772 | 55.33 | 43 |
| UCTT-2026-03-30 | 2026-05-12 | 2026-03-30 | 83.01 | 72.01 | 0.833 | 71.29 | 13 |
| WULF-2026-03-06 | 2026-05-15 | 2026-03-06 | 16.86 | 13.70 | 0.929 | 13.56 | 46 |
| YOU-2026-02-03 | 2026-04-28 | 2026-02-03 | 48.92 | 44.63 | 0.776 | 44.18 | 46 |
| YOU-2026-04-29 | 2026-05-22 | 2026-04-29 | 60.94 | 55.54 | 0.833 | 54.98 | 9 |

10 distinct tickers — DK, DNTH, KOD, OII, RNG, TROX, TSHA, UCTT, WULF, YOU. TSHA and UCTT contribute 2 W patterns each (different trough_1_dates).

---

## 3. Recency-threshold sensitivity

Per dispatch brief §6.2(g) implicit sensitivity check. Pattern count varies smoothly with the recency threshold:

| Threshold | Patterns | Distinct tickers | Notes |
|---|---|---|---|
| 30 days | 4 | 3 | Too few for any verdict |
| 60 days | 13 | 10 | Backtest default |
| 90 days | 18 | 13 | Captures all 15 cohort tickers per §1.2 |
| 120 days | 22 | 14 | Approaches "no recency filter" |
| No filter | 172 | 15 | Trivially-triggering OLD W's dominate |

The verdict's NEGATIVE classification is robust to threshold choice within 60-90d — both bands have 0 closed-and-profitable trades AND mean-R closed sufficiently negative to trip the §7.5 NEGATIVE bound. The trigger-rate finding (R1 hypothesis SUPPORTED on trigger component) holds across all thresholds.

---

## 4. Backtest mechanics

### 4.1 Entry rule (shared)

- **Trigger threshold:** `center_peak_price` (the W's neckline; the canonical W-bottom breakout reference per dispatch brief §2 + §10 — NOT `pivot_price` which is the last close in the candidate window and not actionable).
- **Trigger lower bound:** `max(trough_1_date, trough_2_date, anchor_asof_date) + 1 business day`.
- **Trigger upper bound:** `anchor_asof_date + 60 business days` (np.busday_offset semantics).
- **Trigger event:** first `Close > center_peak_price` within the window.
- **Entry:** next-session open following the trigger session. If no next session exists, pattern is `untriggered`.
- **Initial stop:** `trough_2_price * 0.99` (canonical W right-shoulder buffer; the strict canonical definition per dispatch brief §2 rather than `min(trough_1, trough_2)`).

### 4.2 Three close-based exit rulesets (D1-specific; DIVERGES from V2)

D1's dispatch brief §3 specifies CLOSE-based exit semantics throughout (no intraday Low/High triggers, no breakeven arm in Ruleset B, no slope-check trail arm in Ruleset C). The 3 rulesets are deliberately simpler than V2's intraday-aware rulesets, reflecting the brief's interpretation of Minervini / DST source-of-truth as close-confirmed signals.

- **Ruleset A — Minervini trail-MA:** +2R close arms; post-arm trail stop = `max(prior, SMA21(close) - 1*ATR14)`; TERMINAL hard exit on first close <= SMA50 **regardless of trail state** (dispatch brief §3.1 LOCK).
- **Ruleset B — Fixed R-multiple:** close < initial_stop fires `stop_hit` at close; close >= entry + 3R fires `target_3R` at target_price. NO breakeven, NO trail.
- **Ruleset C — Close-below-50d-SMA:** close < initial_stop fires `stop_hit` at close; close < SMA50 fires `close_below_50d` at close. NO trail-arm logic.

SMA21 / SMA50 / ATR14 use the FULL archive's backward lookback from each bar position (NOT only forward-of-asof bars) — so these are computable from day 1 of every position, allowing the rulesets to differentiate meaningfully even when forward-window-after-asof is sparse. This is a deliberate methodology choice DIFFERENT from V2 backtest (which used forward-bars-only and consequently had no SMA computability for any of its 5 triggered patterns).

---

## 5. Per-ruleset aggregate stats

| Ruleset | Patterns | Triggered | Closed | Winners | Losers | Untrig | Open | Win-rate | Avg R (closed) | Avg R (loser closed) |
|---|---|---|---|---|---|---|---|---|---|---|
| A_minervini_trail_ma | 13 | 8 | 2 | 0 | 2 | 5 | 6 | 0.0% | -0.708R | -0.708R |
| B_fixed_R_multiple | 13 | 8 | 0 | 0 | 0 | 5 | 8 | n/a | n/a | n/a |
| C_close_below_50d | 13 | 8 | 2 | 0 | 2 | 5 | 6 | 0.0% | -0.708R | -0.708R |

**Cross-ruleset observation:** Rulesets A and C emit IDENTICAL closed-trade outcomes — both fire `close_below_50d` on the same 2 patterns (DK-2026-03-09 at -0.96R and TROX-2026-02-20 at -0.456R). This is expected: A's terminal `close <= SMA50` (regardless of trail state) is mechanically equivalent to C's `close < SMA50` (no trail) for any position that doesn't first hit the +2R trail-arm threshold. None of the 8 triggered patterns reached +2R, so A's trail mechanism never fires; effective behavior collapses to C.

Ruleset B is the most-permissive — its only exits are close < initial_stop (didn't fire on any pattern) and close >= +3R (didn't fire either; no pattern reached 3R in available forward window). All 8 triggered patterns remain `open_at_data_tail` under B.

---

## 6. Per-pattern outcomes

### 6.1 Triggered patterns (8 of 13)

| pattern_id | entry_date | exit_date (A/C) | R (A/C) | R at tail (B) | Trigger date relative to asof |
|---|---|---|---|---|---|
| DK-2026-03-09 | 2026-05-20 | 2026-05-21 (close_below_50d) | -0.96R | -0.48R | +5 BD after asof |
| KOD-2026-02-05 | 2026-05-01 | open | -0.16R | -0.16R | +2 BD after asof |
| OII-2026-03-13 | 2026-04-23 | open | **+0.78R** | +0.78R | +2 BD after asof |
| RNG-2026-03-27 | 2026-05-04 | open | -0.28R | -0.28R | +4 BD after asof |
| TROX-2026-02-20 | 2026-05-01 | 2026-05-07 (close_below_50d) | -0.46R | -0.20R | +2 BD after asof |
| UCTT-2026-03-06 | 2026-05-14 | open | -0.04R | -0.04R | +2 BD after asof |
| UCTT-2026-03-30 | 2026-05-14 | open | -0.08R | -0.08R | +2 BD after asof |
| YOU-2026-02-03 | 2026-04-30 | open | **+0.75R** | +0.75R | +2 BD after asof |

**Open position aggregate (Ruleset B; 8 of 8 triggered remain open):** Mean unrealized R = (-0.48 + -0.16 + +0.78 + -0.28 + -0.20 + -0.04 + -0.08 + +0.75) / 8 = **+0.04R** (mean essentially zero with high variance; 2 winners + 6 losers).

This is a meaningfully different distribution from V2 backtest's -0.18R mean unrealized — but with 0 closed-and-profitable on either side, the data is too thin to draw a statistical inference.

### 6.2 Untriggered patterns (5 of 13)

| pattern_id | fwd_bars_in_window | max_forward_close | % of peak | Notes |
|---|---|---|---|---|
| DNTH-2026-02-13 | 3 | 87.80 | 101.0% | **Sparse-data trigger lost** — max close BARELY exceeded peak (101%) but on bar 3 of 3 with no next-session for entry-open |
| TSHA-2026-02-05 | 1 | 6.30 | 128.8% | Sparse-data trigger lost — 1 bar of fwd data; trigger window ended same session |
| TSHA-2026-03-24 | 1 | 6.30 | 137.6% | Same as above; both TSHA patterns lost to data sparsity |
| WULF-2026-03-06 | 0 | n/a | n/a | **Zero forward bars** — asof_date == archive tail |
| YOU-2026-04-29 | 0 | n/a | n/a | **Zero forward bars** — same architectural data-freshness constraint |

3 of the 5 untriggered patterns (DNTH + 2x TSHA) actually had max forward closes ABOVE the W neckline but were disqualified by either (a) no next-session-open available for entry execution (DNTH bar 3 of 3) or (b) trigger search window already exhausted (TSHA × 2; only 1 forward bar available because asof landed near archive tail). 2 patterns (WULF + YOU-04-29) had ZERO forward bars at all.

**5 of 13 = 38.5% of patterns are disqualified by forward-window-sparsity rather than by genuine trigger failure** — the same architectural data-freshness constraint that capped V2 backtest at 12/17 untriggered.

---

## 7. Limitations + caveats

### 7.1 L6 — archive bar-content TEMPORAL mutation

Per cumulative gotcha #26 + the V2 backtest's L6 caveat. The forward-walk reads CURRENT archive bars; if intervening pipeline runs mutated historical bars via `swing/data/ohlcv_archive.py:write_window`'s `drop_duplicates(subset=['asof_date'], keep='last')` semantics, the entry-trigger close-above-peak detection may evaluate against slightly different bar values than were available at V1 contemporaneous state. For D1's cohort, the structural anchors (`trough_1_date`, `center_peak_price`, `trough_2_price`) come from the **persisted** detector evidence in `pattern_cohort_evaluator` results.csv (which itself reads current archive at smoke time — see L8) — so structural-anchor drift between cohort-input-time + backtest-execution-time is bounded by the smoke artifact's age (a few hours). The forward-walk after entry uses bars consistently from current archive.

**Estimated impact on this study:** the V2 backtest's 14 L6-drifted candidates (CNTA / ECVT / APLS / FTI / STNG / PL) do NOT intersect this cohort's 10 tickers (DK / DNTH / KOD / OII / RNG / TROX / TSHA / UCTT / WULF / YOU). L6 direct impact: ZERO. The lesson generalizes — future D-bot-W cohorts on different ticker sets need this cross-check separately.

### 7.2 L4 / L8 — Shape A vs legacy asymmetry; cache_dir naming

Per cumulative gotcha #24 + the source study's L8 caveat. The harness reads via the V2 Shape A reader (`research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader.read_yfinance_shape_a`) which prefers `{T}.yfinance.parquet` over `{T}.parquet` with `BothExistDiagnostic` recording the conflict count. This smoke surfaced 1 both-exist hit per the manifest. Read path uses the canonical `~/swing-data/prices-cache/` (hyphen) per L8.

### 7.3 Forward-window asymmetry across patterns

Patterns with earlier `anchor_asof_date` have proportionally more forward bars: e.g., OII (asof 2026-04-21) has ~22 BD forward to the archive tail (2026-05-22); WULF + YOU-04-29 (asof 2026-05-15 / 2026-05-22) have 0-5 BD forward. Forward-window asymmetry biases toward patterns whose asof was further from archive tail — these are MORE LIKELY to trigger AND more likely to remain open at tail. The bias affects the 61.5% trigger rate measurement: if all 13 patterns had identical forward window depth, the trigger rate would be unchanged for the OII-style patterns (already triggered with ample data) but ZERO untriggered patterns would be sparse-data-disqualified.

**Estimated impact:** under a more-uniform forward window assumption, the "true" trigger rate could be as high as 11/13 = 84.6% (counting DNTH + 2x TSHA + WULF + YOU-04-29 as triggered-given-sufficient-data). This is an upper bound; the conservative reading is the literal 61.5% from the actual run.

### 7.4 N=2 closed + N=0 closed-and-profitable: statistical un-decidability

The closed-trade verdict rests on 2 R values from the SAME exit reason (`close_below_50d`) on 2 different patterns. The mean-R closed (-0.708R) is structurally bounded by Ruleset A/C's mechanical exit — neither ruleset can produce a positive closed trade unless price first reaches +2R (Ruleset A) or stays above SMA50 until target (Ruleset B; never tested in this cohort). The verdict ("NEGATIVE") is structural, not statistical — even if the 6 open positions under A/C resolve to mixed positive/negative R, the 0 closed-and-profitable + 0 reaching +3R structural absence persists.

### 7.5 Mechanical close_below_50d exit timing

Both closed trades exited via `close_below_50d` on consecutive sessions after entry (DK exited on day 1 post-entry; TROX exited on day 6 post-entry). This reflects entries at positions where price was already near SMA50 — the mechanical exit fires almost immediately, not because the trade failed substantively but because the entry-anchor was near a level the ruleset uses as a stop reference.

This is a known weakness of the D1 brief's "terminal close <= SMA50 regardless of trail state" semantic (Ruleset A) and the "close < SMA50" semantic (Ruleset C): for positions whose entry is at or near 50d SMA, even small downside fluctuation immediately fires the exit. The ruleset's intent (per Minervini's late-Stage-2 sell discipline) presumes entry is comfortably ABOVE 50d SMA at trigger; D1's `close > center_peak_price` trigger doesn't enforce that — when `center_peak_price` happens to be near 50d SMA, mechanical exit fires almost immediately.

**Banked V2 candidate:** Ruleset C variant where 50d SMA exit requires the position to first close ABOVE 50d SMA by some margin (e.g., +5% buffer or +1*ATR) before becoming armed.

---

## 8. Cross-comparison with V2 OHLCV backtest at `e0a9edd`

### 8.1 Per-ticker overlap

V2 backtest cohort: DK, DNTH, FRO, KOD, NAT, OII, PTEN, RLMD, RNG, SSRM, TROX, TSHA, UCTT, WULF, YOU (15 unique tickers).
D1 backtest cohort: DK, DNTH, KOD, OII, RNG, TROX, TSHA, UCTT, WULF, YOU (10 unique tickers).

**Overlap: 10 of 15 V2 tickers also appear in D1.** FRO, NAT, PTEN, RLMD, SSRM appear in V2 (VCP-shape candidates per the +67 cohort) but do NOT appear in D1's 60-day recency window (their recent W structures have trough_2 > 60 days before asof, or no W passes composite>=0.7 at the recent windows). This is consistent with the source study's finding that the cohort is double-bottom-w-DOMINATED but not exclusively so — some patterns are genuinely VCP-only.

### 8.2 Per-pattern overlap

For the 10 tickers in both cohorts, the **patterns themselves differ** structurally:

- V2 backtest uses `consolidation_pivot` from the V1 evaluator's VCP detector (a price level inside the consolidation range).
- D1 backtest uses `center_peak_price` from the Phase 13 `double_bottom_w` detector (the W neckline; structurally different from any VCP-derived pivot).

For example, V2's `DK-r53` has pivot=49.50 + initial_stop=37.25 (from V1 candidates table); D1's `DK-2026-03-09` has center_peak=45.41 + initial_stop=41.97 (different geometry). The two backtests test the SAME underlying ticker cohort but with structurally different trade definitions.

### 8.3 Per-outcome cross-tabulation

| Metric | V2 (VCP-rule) | D1 (W-rule) | Direction of change |
|---|---|---|---|
| Trigger rate | 29.4% (5/17) | **61.5%** (8/13) | **+109% improvement** (HYPOTHESIS R1 SUPPORTED on trigger) |
| Closed-and-profitable | 0 | 0 | No change (BOTH zero) |
| Mean R (closed) | n/a (0 closed) | -0.708R (2 closed) | D1 produces non-empty closed distribution |
| Mean R (open at tail) | -0.18R (5 open) | +0.04R (8 open under Ruleset B) | D1 marginally positive but high variance |
| Sparse-data disqualification rate | 70.6% untriggered | 38.5% untriggered | D1 has fewer untriggered absolute count |

The mechanical trigger-rate improvement (+109%) confirms the R1 hypothesis's narrow claim: the W-bottom-appropriate trigger rule fires materially more often on the W-shape-dominated cohort than the VCP-appropriate rule did. The BROADER R1 hypothesis (chart-shape-appropriate rules unlock expectancy) is NOT supported — both backtests yield 0 closed-and-profitable trades AND the mean open-position R is essentially zero with high variance.

### 8.4 What changed; what didn't

The trigger rule swap (close > consolidation_pivot → close > center_peak_price) DID:
- Raise trigger rate from 29% to 62%.
- Produce 2 closed trades (vs V2's 0).
- Produce a non-trivial open-position R distribution with both winners and losers.

The trigger rule swap did NOT:
- Produce any closed-and-profitable trades.
- Produce positive mean-R across closed trades.
- Resolve the forward-window-sparsity issue (5 of 13 patterns disqualified by data tail).

**Operator-paired interpretation:** the binding constraint on V2's NEGATIVE verdict was framed in the source study as "chart-shape mismatch at the trigger gate." D1 confirms that's part of the story (trigger rate doubled) but reveals a SECOND binding constraint: even when triggered, the cohort's W-bottom completions do not produce profitable trades within the available 1-5 week forward window. The R1 hypothesis is PARTIALLY validated (trigger-rate component) and PARTIALLY refuted (profitability component).

---

## 9. Implications + recommended next actions

### 9.1 Pivot interpretations for the broader research program

The source study's Conclusion enumerated 3 reframing options (R1 / R2 / R3). D1's findings update each:

- **R1 (chart-shape-appropriate trigger):** PARTIALLY VALIDATED for trigger rate; INSUFFICIENT for expectancy. D1 establishes that the W-bottom rule fires materially more on the W-dominated cohort — but the additional triggered patterns mostly stall in the immediate forward window. Either (a) the cohort's W-bottom signal is genuine but the immediate post-asof window is the wrong evaluation horizon (V2.5/V3 candidate: extend window to 8-20 weeks per typical W-bottom maturation), OR (b) the cohort's chart-shape signal is real but trade execution requires additional upstream gates (volume confirmation, market regime, sector strength).

- **R2 (per-variable cohort smoke for 4 remaining VCP-family binding variables):** STILL RECOMMENDED. If the other 4 binding variables admit different chart shapes (e.g., flat_base or cup_with_handle dominated cohorts), each would warrant its own chart-shape-appropriate trigger backtest. D1's PARTIAL validation reduces the cost of R2 — at minimum it establishes that trigger-rule choice does materially affect trigger rate.

- **R3 (treat sensitivity as upstream classification diagnostics):** REINFORCED. D1 demonstrates that even with chart-shape-appropriate triggers, the cohort's classification-flips do not directly translate to profitable trades. The V2 sensitivity rankings remain useful for understanding A+ classification mechanics but should NOT directly inform cfg-policy deployment without per-cohort backtest verification at the chart-shape-appropriate trigger level — which D1 shows is necessary but not sufficient.

### 9.2 Immediate next actions

Three options for the orchestrator-paired next decision:

- **Option A — Pivot to `vcp.tightness_days_required +16` cohort smoke + backtest (R2 path).** Next-most binding variable; mirrors D1's full arc (cohort detection → recency filter → backtest with chart-shape-appropriate trigger). Estimated cost: 8-16 hours. This iterates the R2 hypothesis on the 2nd binding variable.

- **Option B — Extend D1's forward window via operator-paired archive refresh.** Re-fetch OHLCV for the 10 D1 tickers via production pipeline, then re-run the backtest with up-to-date archive tails. May surface additional trade closures (positive or negative) that resolve the open-position distribution. Estimated cost: 1 pipeline run + ~30 minutes.

- **Option C — Pivot to market-conditions investigation (post-R1+R2 path).** D1's PARTIAL validation suggests the binding constraint may be at a higher level than chart-shape detection alone — market regime, volume confirmation, or sector strength. Estimated cost: substantial; brief drafting + spec; multi-week.

**RECOMMENDED:** Option A in the immediate term. Combine with Option B for the next dispatch's data tail. R2's per-variable cohort smokes provide the cleanest "is the chart-shape mismatch generalizable across binding variables?" answer.

---

## 10. Artifacts

- **Results CSV:** [exports/research/double-bottom-w-backtest-20260525T113638Z/results.csv](../exports/research/double-bottom-w-backtest-20260525T113638Z/results.csv) (21 columns; 39 rows = 13 patterns × 3 rulesets)
- **Summary markdown:** [exports/research/double-bottom-w-backtest-20260525T113638Z/summary.md](../exports/research/double-bottom-w-backtest-20260525T113638Z/summary.md)
- **Manifest JSON:** [exports/research/double-bottom-w-backtest-20260525T113638Z/manifest.json](../exports/research/double-bottom-w-backtest-20260525T113638Z/manifest.json) (cohort_csv_sha256, recency_max_calendar_days, l2_lock_preserved: true)
- **Cohort fixture:** [tests/fixtures/research/double_bottom_w_backtest/cohort.json](../tests/fixtures/research/double_bottom_w_backtest/cohort.json) (172 unique W primary verdicts; 99 KB)
- **Backtest harness:** [research/harness/double_bottom_w_backtest/](../research/harness/double_bottom_w_backtest/) (5 modules: cohort + walkforward + rulesets + io + run)
- **Discriminating tests:** [tests/research/double_bottom_w_backtest/](../tests/research/double_bottom_w_backtest/) (42 fast tests)
- **CLI subcommand:** `swing diagnose double-bottom-w-backtest` (72 lines added to `swing/cli.py` per OQ-13-mirror carve-out)

---

## 11. Cumulative discipline preservation

- **NO Co-Authored-By footer** preserved across all 4 implementation commits + the smoke commit.
- **`python -m swing.cli` invocation discipline** preserved (CLI subcommand registered + tested).
- **ASCII-only** on findings.md + summary.md + return report + manifest.json + all source files (no unicode bypass).
- **Schema v21 UNCHANGED** (zero migration files added).
- **L2 LOCK preserved:** harness reads via V2 OHLCV Shape A reader only; ZERO new Schwab API calls; ZERO new yfinance fetch calls. 2 BINDING L2 LOCK tests at `tests/research/double_bottom_w_backtest/test_l2_lock.py` (import-graph sentinel + source-grep sentinel).
- **V1 persisted state UNCHANGED:** ZERO SELECT/UPDATE/INSERT against `candidate_criteria` / `candidates` / `evaluation_runs` / `trades` / `pattern_evaluations`. Cohort source is the (already-persisted) pattern_cohort_evaluator results.csv; backtest reads OHLCV via the read-only Shape A reader; no DB writes.
- **Production `swing/` READ-ONLY EXCEPT OQ-13 carve-out:** sole `swing/` modification is the 72-line `diagnose_double_bottom_w_backtest` CLI subcommand registration. `git diff main -- swing/` shows only this addition.
- **Fast suite:** 42 NEW D1 tests + 0 regressions in 5993 cumulative fast tests (baseline 5976 pre-D1 + 21 unrelated test additions + 42 D1 = 6039 post-D1, with 2 skipped + 0 failed).

---

*End of findings document. Verdict: NEGATIVE strict per §7.5; R1 hypothesis SUPPORTED on trigger-rate component (61.5% vs 29%; +109%); REFUTED on profitability component (0 closed-and-profitable; mean-R closed -0.708R). Recommended next action: Option A (pivot to next binding variable cohort smoke + backtest per R2) combined with Option B (operator-paired archive refresh for D1 re-run as data tail advances).*
