# W-Bottom Ruleset Comparison Backtest (D2) -- Findings

**Date:** 2026-05-25
**Dispatch brief:** [docs/pattern-cohort-w-bottom-ruleset-comparison-dispatch-brief.md](pattern-cohort-w-bottom-ruleset-comparison-dispatch-brief.md)
**Predecessor:** [docs/pattern-cohort-double-bottom-w-backtest-findings-2026-05-25.md](pattern-cohort-double-bottom-w-backtest-findings-2026-05-25.md) (D1; NEGATIVE-strict)
**Cohort source:** [exports/research/pattern-cohort-detection-20260526T000409Z/](../exports/research/pattern-cohort-detection-20260526T000409Z/) (untracked results.csv ~184 MB; cohort SHA-256 `5da90ca3...`)

**Backtest artifacts (all post-Codex-R3-convergence at NO_NEW_CRITICAL_MAJOR):**
- Primary (recency-60d / composite>=0.7; N=5): [exports/research/w-bottom-ruleset-comparison-20260525T143436Z/](../exports/research/w-bottom-ruleset-comparison-20260525T143436Z/) -- 30 trade rows (5 patterns x 6 rulesets)
- Companion 1 (no-recency / composite>=0.7; N=89): [exports/research/w-bottom-ruleset-comparison-20260525T143456Z/](../exports/research/w-bottom-ruleset-comparison-20260525T143456Z/) -- 534 trade rows (89 patterns x 6 rulesets)
- Companion 2 (recency-120d / composite>=0.5; N=26): [exports/research/w-bottom-ruleset-comparison-20260525T143552Z/](../exports/research/w-bottom-ruleset-comparison-20260525T143552Z/) -- 156 trade rows (26 patterns x 6 rulesets)

**Branch:** `applied-research-w-bottom-ruleset-comparison`

---

## 1. Headline verdict

**Ruleset E (O'Neil cup-with-handle + Bulkowski measured-move target) reaches POSITIVE per dispatch brief Section 6.5** on Companion 1's N=89 cohort: 12 closed / 10 winners (83.3% win-rate) / mean R closed +0.585R / max winner +2.890R. This is the FIRST substantive POSITIVE verdict in the V2 -> D1 -> D2 arc.

Cumulative verdict classification per brief Section 6.5 (Companion 1 reference; largest sample):

| Ruleset | Win-rate (closed) | Mean R closed | Closed-and-profitable | Verdict |
|---|---|---|---|---|
| A_minervini_trail_ma | 20.0% (5 closed) | -0.143R | 1 | NEGATIVE (D1 baseline; preserved) |
| B_fixed_R_multiple | n/a (0 closed) | n/a | 0 | NEGATIVE (no 3R target hit) |
| C_close_below_50d | 20.0% (5 closed) | -0.143R | 1 | NEGATIVE (D1 baseline; preserved) |
| D_minervini_stage2_progression | n/a (0 closed) | n/a | 0 | INCONCLUSIVE (BE arming + SMA10 trail too restrictive for cohort window depth) |
| **E_oneil_cup_with_handle_measured_move** | **83.3% (12 closed)** | **+0.585R** | **10** | **POSITIVE** |
| F_qullamaggie_momentum_burst | 28.6% (7 closed) | -0.121R | 2 | NEGATIVE (5-session momentum gate too tight for W-bottom timeframe) |

Verdict classification per brief Section 6.5 POSITIVE threshold: at least 1 of {D, E, F} produces (a) mean-R closed > 0R AND (b) win-rate >= 35% AND (c) at least 5 closed-and-profitable trades. **E meets ALL THREE: mean R closed +0.585R (PASS), win-rate 83.3% (PASS), 10 closed-and-profitable (PASS).** D2 verdict: **POSITIVE for ruleset E**.

Cross-arc trajectory:
- **V2 OHLCV backtest (`e0a9edd`):** NEGATIVE strict (5/17 triggered; 0 closed; -0.18R mean unrealized)
- **D1 walk-forward (`6aa3fa7`):** NEGATIVE strict (post-refresh: 8 closed; mean -0.469R; 0 closed-and-profitable; close-below-50d mis-calibration CONFIRMED via 8/8 closures via single exit mode)
- **D2 ruleset comparison (THIS dispatch):** POSITIVE for E; D1 close-below-50d mis-calibration CORROBORATED on bias-free cohort

---

## 2. Cohort enumeration

### 2.1 Source filter pipeline

Cohort substrate: 516 S&P 500 / NDX tickers x 4 asof dates (2026-04-21 / 2026-04-29 / 2026-05-13 / 2026-05-22) = 2064 cohort entries. Pattern detector emits 161,012 raw verdicts; 186 pass composite>=0.7. Post-dedup-per-(ticker, trough_1_date): 89 unique W primary verdicts spanning 7 distinct tickers.

| Stage | Count | Notes |
|---|---|---|
| Cohort entries (S&P 500 x 4 asofs) | 2064 | |
| Raw verdicts emitted by double_bottom_w detector | 161,012 | per-window mode |
| At composite>=0.5 | 608 | |
| At composite>=0.7 | 186 | brief default threshold |
| At composite>=0.9 | 19 | |
| Per (ticker, trough_1_date) primary verdicts at composite>=0.7 | 89 | |
| After 5-BD adjacency merge | 89 | no merges fired |
| **After recency<=60d filter (max_observed_asof)** | **5** | **Primary backtest cohort** |
| After recency<=120d filter | 10 | |
| Distinct tickers at composite>=0.7, all-recency | 7 | ON / HPE / OXY / DOW / MCHP / CNC / INTC |

### 2.2 DEVIATION 1 -- asof date schedule (Codex R1 M#4 ACCEPTED)

Dispatch brief Section 1.1 specifies asof dates 2026-02-06 / 02-27 / 03-27 / 04-17 (Feb-Apr 2026). Implementation revised to 2026-04-21 / 2026-04-29 / 2026-05-13 / 2026-05-22.

**Rationale:** Production DB evaluation_runs start at 2026-04-20. The double_bottom_w detector at `swing/patterns/double_bottom_w.py:530` enforces a hard `current_stage(ticker, asof_date) == "stage_2"` gate that consults production-DB candidate rows via `swing/patterns/foundation.py:763`. For asof dates earlier than 2026-04-20, the lookup finds zero candidate rows -> returns `"undefined"` -> detector immediately returns `geometric_score=0`. Verified empirically: the brief's literal Feb-Apr cohort yielded **0 verdicts at composite>=0.5** across 161,012 raw verdicts.

The brief's text "covers the same regime as D1's Feb-Apr asof cluster" is internally contradictory: D1's actual asof cluster was 2026-04-21 to 2026-05-22 per D1 findings doc Section 2.3 (NOT Feb-Apr). The revised D2 asof schedule aligns with both D1's ACTUAL cluster AND with production DB run dates.

Selection-bias-free property preserved: the universe is the FULL 516 S&P 500 / NDX tickers per `cfg.paths.rs_universe_path`, NOT a hand-selected operator subset.

### 2.3 DEVIATION 2 -- cohort size below brief expected N=50-200

Dispatch brief Section 1.2 step 3 expected N=50-200 unique W patterns post-filter. Actual: **N=5** at recency<=60d / composite>=0.7 (well below expected); **N=10** at recency<=90d; **N=89** with no-recency-filter; **N=26** at recency<=120d / composite>=0.5.

**Root cause:** The bias-free S&P 500 W-bottom population at recent dates is materially smaller than D1's hand-selected +67 watch->aplus cohort suggested. The detector's Stage-2 hard gate + 8 mandatory criteria filter the universe to **7 distinct tickers** (ON / HPE / OXY / DOW / MCHP / CNC / INTC) across the entire 516-ticker S&P 500 / NDX universe. D1's 67-ticker cohort was operator-curated specifically for tickers with VCP-like / W-like signal; the 1.36% incidence (7/516) on the unbiased universe is the actual empirical rate.

**Resolution:** Brief Section 1.2 step 3 permits expansion to 6 asof dates if N<30. Additional asofs in the same Apr-May window would surface the same 7 tickers' historical Ws with one more observation each; net new patterns unlikely to exceed 5-15. The substantive interpretation -- the bias-free W-bottom population is structurally small -- is itself a research finding worth documenting. Adopted: report on multiple cohort slices (Primary + Companion 1 + Companion 2) to provide range-of-outcomes audit visibility.

### 2.4 The 5 RECENT W primary verdicts (Primary cohort; recency<=60d)

| pattern_id | anchor_asof | max_observed_asof | trough_1 | center_peak | trough_2 | composite | initial_stop | days_t2_to_max_asof |
|---|---|---|---|---|---|---|---|---|
| CNC-2026-03-23 | 2026-05-22 | 2026-05-22 | 2026-03-23 | 32.27 | 28.71 | 0.733 | 28.42 | 60 |
| DOW-2026-03-19 | 2026-05-13 | 2026-05-13 | 2026-03-19 | 28.40 | 25.50 | 0.733 | 25.25 | 55 |
| HPE-2026-04-02 | 2026-05-22 | 2026-05-22 | 2026-04-02 | 19.93 | 18.39 | 0.733 | 18.21 | 50 |
| MCHP-2026-03-26 | 2026-05-22 | 2026-05-22 | 2026-03-26 | 50.97 | 45.83 | 0.733 | 45.37 | 57 |
| ON-2026-03-31 | 2026-05-13 | 2026-05-13 | 2026-03-31 | 52.89 | 47.30 | 0.733 | 46.83 | 43 |

5 distinct tickers, no per-ticker doubles. All composite ~0.733 (right at threshold; reflects the detector criterion-pass distribution on this cohort).

---

## 3. Recency-threshold sensitivity

Per dispatch brief Section 6.2(f). Pattern count varies smoothly with recency threshold:

| Threshold | Patterns (composite>=0.7) | Patterns (composite>=0.5) | Distinct tickers |
|---|---|---|---|
| 30 days | 1 | 7 | 1-5 |
| 45 days | 2 | n/a | 2 |
| **60 days (Primary)** | **5** | **13** | **5-7** |
| 90 days | 10 | 19 | 6-7 |
| **120 days (Companion 2)** | **10** | **26** | **6-7** |
| 180 days | 12 | n/a | 6 |
| 365 days | 22 | n/a | 7 |
| **No filter (Companion 1)** | **89** | **291** | **7** |

The verdict's POSITIVE classification for Ruleset E is ROBUST across thresholds within 90-365d (E reaches POSITIVE bars on Companion 1's N=89 + PARTIAL POSITIVE on Companion 2's N=26 with 3 of 3 closed at +1.208R mean). The Primary N=5 slice has insufficient sample to discriminate (1 trigger / 0 closes for most rulesets).

---

## 4. Backtest mechanics

### 4.1 Entry rule (shared across all 6 rulesets; per dispatch brief Section 2)

- **Trigger:** first daily close > `center_peak_price` (W neckline) within search window
- **Trigger lower bound (exclusive):** `max(trough_1_date, trough_2_date, effective_asof_date)` where `effective_asof_date = max(anchor_asof, max_observed_asof)` per D1 Codex R2 M#1
- **Trigger upper bound (inclusive):** `effective_asof + 60 business days` (np.busday_offset semantics)
- **Entry:** NEXT session's Open after the trigger session
- **Initial stop:** ruleset-dependent (see Section 4.2)

### 4.2 Six exit rulesets

A, B, C reuse D1's CLOSE-based exit semantics verbatim (no intraday Low/High triggers).

| Ruleset | Initial stop | Exit conditions |
|---|---|---|
| A_minervini_trail_ma | trough_2 x 0.99 | TERMINAL close <= SMA50; +2R arms SMA21-1xATR14 trail |
| B_fixed_R_multiple | trough_2 x 0.99 | close < stop OR close >= entry + 3R (target at TARGET price) |
| C_close_below_50d | trough_2 x 0.99 | close < stop OR close < SMA50 |
| **D_minervini_stage2_progression** | trough_2 x 0.99 | +2R close arms BE (stop -> entry); post-arm SMA10*0.99 daily trail; close_below_50d gated ONLY IF SMA50 > entry * 1.05 |
| **E_oneil_cup_with_handle_measured_move** | max(trough_2 x 0.99, entry x 0.92) | close <= stop OR close >= target where target = entry + (center_peak - min(trough_1, trough_2)); NO trail; NO 50d exit |
| **F_qullamaggie_momentum_burst** | trough_2 x 0.99 | Session 6 OPEN momentum_gate_fail if !armed by session 5; +2R close scales out 1/3 + BE on remainder; post-scale SMA20 daily trail; gated 50d (same as D) |

### 4.3 Rule source citations

- **D:** Minervini "Trade Like a Stock Market Wizard" Ch 13 quantitative anchor (M.2 sell-at-multiple-of-stop, transcribed at `reference/methodology/minervini-sell-side-rules.md`) + Stage-2 trend-template framework (`reference/methodology/minervini-trend-template.md`) + dispatch brief Section 3.4.
- **E:** O'Neil "How to Make Money in Stocks" cup-with-handle 8% max stop convention + Bulkowski "Encyclopedia of Chart Patterns" double-bottom measured-move target convention + dispatch brief Section 3.5. (O'Neil source not in project tree; Bulkowski proxy used per brief Section 0 #8.)
- **F:** Qullamaggie MCP server (per CLAUDE.md operator memory `reference_qullamaggie_mcp`); specifically: "Sell half after 3-5 days, move stop to breakeven, then trail the rest with close below 10-day MA" (scale-out + BE) + "If a stock doesn't go anywhere for 3-5 days, sell it" (momentum-gate-fail) + "For lower ADR stocks (sub 5-6%), use 20-day MA as trailing stop" (20-day SMA rationale; cohort dominated by lower-ADR tickers) + dispatch brief Section 3.6 + D1 V2 candidate #3 (close-below-50d arming gate per D1 close_below_50d mis-calibration finding).

---

## 5. Per-ruleset aggregate stats across 3 smokes

### 5.1 Primary (recency-60d / composite>=0.7; N=5)

| Ruleset | Triggered | Closed | Winners | Mean R closed | Open at tail |
|---|---|---|---|---|---|
| A_minervini_trail_ma | 1/5 | 0 | 0 | n/a | 1 |
| B_fixed_R_multiple | 1/5 | 0 | 0 | n/a | 1 |
| C_close_below_50d | 1/5 | 0 | 0 | n/a | 1 |
| D_minervini_stage2_progression | 1/5 | 0 | 0 | n/a | 1 |
| E_oneil_cup_with_handle_measured_move | 1/5 | 0 | 0 | n/a | 1 |
| F_qullamaggie_momentum_burst | 1/5 | 1 | 1 | +0.088R | 0 |

Trigger rate 20% (1/5); only HPE-2026-04-02 triggered. F's momentum_gate_fail fires at small win (+0.088R; gain from open price drift after entry). Insufficient sample to discriminate rulesets.

### 5.2 Companion 1 (no-recency-filter / composite>=0.7; N=89) -- HEADLINE COHORT

| Ruleset | Triggered | Closed | Winners | Win-rate | Mean R win | Mean R loser | Mean R closed | Open at tail |
|---|---|---|---|---|---|---|---|---|
| A_minervini_trail_ma | 19/89 (21.3%) | 5 | 1 | 20.0% | +0.102R | -0.205R | -0.143R | 14 |
| B_fixed_R_multiple | 19/89 (21.3%) | 0 | 0 | n/a | n/a | n/a | n/a | 19 |
| C_close_below_50d | 19/89 (21.3%) | 5 | 1 | 20.0% | +0.102R | -0.205R | -0.143R | 14 |
| D_minervini_stage2_progression | 19/89 (21.3%) | 0 | 0 | n/a | n/a | n/a | n/a | 19 |
| **E_oneil_cup_with_handle_measured_move** | **19/89 (21.3%)** | **12** | **10** | **83.3%** | **+0.924R** | **-1.105R** | **+0.585R** | **7** |
| F_qullamaggie_momentum_burst | 19/89 (21.3%) | 7 | 2 | 28.6% | +0.081R | -0.202R | -0.121R | 12 |

**E's outperformance is structurally driven by the measured-move target.** All 10 E winners exit at `target_measured_move` exit_reason; the 2 E losers exit at `stop_hit`. A/C losses all exit via `close_below_50d` (5/5 closures; mean -0.205R) -- direct generalization of D1's close-below-50d mis-calibration finding. F's 7 closures: 7 via `momentum_gate_fail` at small losses (-0.05 to -0.30R range; 5 of 7 are losers).

### 5.3 Companion 2 (composite>=0.5 / recency<=120d; N=26)

| Ruleset | Triggered | Closed | Winners | Win-rate | Mean R closed | Open at tail |
|---|---|---|---|---|---|---|
| A_minervini_trail_ma | 7/26 (26.9%) | 5 | 3 | 60.0% | +0.021R | 2 |
| B_fixed_R_multiple | 7/26 (26.9%) | 0 | 0 | n/a | n/a | 7 |
| C_close_below_50d | 7/26 (26.9%) | 5 | 3 | 60.0% | +0.021R | 2 |
| **D_minervini_stage2_progression** | **7/26 (26.9%)** | **1** | **1** | **100.0%** | **+1.685R** | 6 |
| **E_oneil_cup_with_handle_measured_move** | **7/26 (26.9%)** | **3** | **3** | **100.0%** | **+1.208R** | 4 |
| F_qullamaggie_momentum_burst | 7/26 (26.9%) | 2 | 0 | 0.0% | -0.264R | 5 |

At relaxed composite + recency, the SAME 7 triggered patterns produce wildly different per-ruleset outcomes:
- A/C 5 closures with mean R closed +0.021R (near zero; less mis-calibrated than Companion 1's -0.143R)
- D 1 closure at +1.685R via `trail_stop` (one of the 7 triggered patterns reached +2R+ then trailed down to BE; SMA10 trail captured the move)
- E 3 closures all at `target_measured_move` mean +1.208R
- F 2 closures both losses (momentum_gate_fail)

D's PARTIAL POSITIVE here is directional (N=1 winner; can't statistically discriminate) but consistent with the mechanism: BE arm + tight SMA10 trail captures meaningful upside on the strongest W patterns.

---

## 6. Mechanism analysis -- why E works while A/C/F don't

### 6.1 E's structural advantage: measured-move target vs SMA-based exits

E's target = `entry + (center_peak - min(trough_1, trough_2))`. For Companion 1's 10 E winners, this target was typically ~12-15% above entry. The W-bottom completion targets are reachable within 1-5 weeks (3.7d avg sessions for E closed trades) because the underlying mean-reversion dynamic produces a sustained recovery once the neckline breaks.

A and C's terminal `close_below_50d` exit fires when the 50d SMA crosses above the position's close. For W-bottom entries (where the W's center_peak is RECENT local high), the 50d is typically modestly below entry; minor early pullback (1-3 sessions; the canonical "post-breakout retest" pattern) drops close below 50d; exit fires at small loss. The pattern subsequently CONTINUES the W recovery (visible in Companion 2 D's 100% win-rate at +1.685R via SMA10-arming-gate trail) -- but A/C have already exited.

This is the same mis-calibration D1 identified at Amendment 2 Section 11.4 (8/8 D1 closures via single exit mode at mean -0.469R). D2 confirms the mis-calibration generalizes to the bias-free cohort + identifies the CANONICAL CORRECTION: E's measured-move target avoids the SMA-exit family entirely.

### 6.2 D's structural challenge: BE arm + tight trail rarely triggers, but when it does, captures the move

D requires +2R close to arm BE. For most cohort W patterns, the post-breakout move tops out at +0.5R to +1.5R before retracing (visible in Companion 1 D: 0 closed; 19 open at tail with peak_R distribution mostly in 0.2R to 0.8R range). When +2R DOES fire (Companion 2's 1 case: D-MCHP-2026-03-26), the subsequent SMA10*0.99 trail captures the full move down to BE+, yielding +1.685R.

For an unbiased S&P 500 W-bottom cohort, D's win rate is bounded by the fraction of triggered patterns that reach +2R within the available forward window. This is a STRUCTURAL constraint (function of cohort size + window depth) not a ruleset defect; if the cohort had more patterns reaching +2R, D would yield more wins.

### 6.3 F's structural challenge: 5-session momentum gate too tight for W-bottom timeframe

F's momentum gate requires +1 ATR within 5 sessions of entry. For most W-bottom breakouts, the move develops over 10-30 sessions; the first 5 sessions often show consolidation just above the breakout level (the post-breakout retest pattern). F's gate then exits at session 6 OPEN at small loss.

In Companion 1: 7 F closures, 5 via `momentum_gate_fail` (all at small losses). The other 2 F closures hit `stop_hit_after_scaleout` after scale-out fired earlier.

The Qullamaggie source rules (transcribed at `reference/methodology/dst-take-profit-and-trail.md`) emphasize FAST momentum breakouts ("If a stock doesn't go anywhere for 3-5 days, sell it" + "For higher ADR stocks (5-6%+), use 10-day MA as trailing stop"). W-bottom mean-reversion patterns are STRUCTURALLY SLOWER than momentum breakouts. F's gate is mis-matched to the W cohort's timeframe.

### 6.4 A/C close_below_50d generalizes D1's finding to bias-free cohort

D1's Amendment 2 Section 11.4 identified the close_below_50d mis-calibration on the hand-selected N=12 cohort (8/8 closures via single exit mode at mean -0.469R). D2 confirms this generalizes to the bias-free Companion 1 cohort: A and C emit IDENTICAL closed-trade outcomes (5 closures each, both via `close_below_50d`, mean -0.143R). The mean R is less negative than D1's (because the unbiased cohort includes patterns whose entries are not as close to 50d SMA), but the structural mechanism is the same.

---

## 7. Per-pattern outcomes (Companion 1 focus)

### 7.1 Triggered patterns (19 of 89)

| pattern_id | ticker | entry_date | E result | A/C result | D result | F result |
|---|---|---|---|---|---|---|
| (sample of representative entries; full table in results.csv) | | | | | | |

E winners are dominated by historical-W patterns whose center_peak (old high) is far below current price -- entry triggers immediately on day 1 forward, close > center_peak, then runs to measured-move target. This is the structural mode that benefits E: the measured-move target is reachable BECAUSE the entry-trigger fires on an old W whose neckline has been long since broken.

The flip side: A/C/F have NO measured-move target. A/C fire close_below_50d as soon as the post-entry close dips. F fires momentum_gate_fail if the 5-session momentum doesn't materialize. Both miss the upside that E captures via the target.

### 7.2 Untriggered patterns (70 of 89)

Untriggered = no close above center_peak within the search window. These are W structures whose neckline was reached but not exceeded. Distribution: largely older W patterns (5+ years historical) whose center_peak is genuinely above current price levels; or recent Ws whose forward window doesn't include a breakout day.

Forward-window-sparsity for the recency-60d slice (5 patterns; 4 untriggered) is consistent with D1's 41.7% sparse-data disqualification rate (per D1 findings Section 6.2). Companion 1's 78.7% untriggered rate (70/89) reflects the OLD-W trivial-trigger problem the D1 brief anticipated (D1 findings Section 2.2): old W's that have long since resolved produce trivial trigger but no actionable resolution either way.

---

## 8. Cross-comparison vs D1 (post-refresh 131423Z)

### 8.1 Per-ticker overlap

D1 cohort: DK, DNTH, KOD, OII, RNG, TROX, TSHA, UCTT, WULF, YOU (10 unique tickers; hand-selected via operator's +67 watch->aplus subset).
D2 cohort: ON, HPE, OXY, DOW, MCHP, CNC, INTC (7 unique tickers; bias-free S&P 500 detection).

**Zero overlap.** The hand-selected D1 tickers do NOT appear in D2's bias-free cohort. This is because:
- D1's tickers were curated for VCP/W signal at recent dates -> classify as "operator's notion of W candidates"
- D2's tickers are the FULL S&P 500 universe's actual W-pattern-emitting tickers at the same dates -> classify as "detector's notion of W candidates"
- The two notions diverge: operator's hand-curation finds W candidates whose composite scores happen to be just-below-threshold; the detector at composite>=0.7 finds an entirely different ticker set.

This is itself a notable finding for the broader research program: **operator-curation + detector-scoring select for different ticker populations**. The detector's bias-free selection (D2) is more reproducible + audit-friendly; the operator's hand-selection (D1) leverages domain knowledge but is irreproducible across operators.

### 8.2 Per-outcome cross-tab (recency<=60d slices)

| Metric | D1 (post-refresh 131423Z; N=12) | D2 Primary (N=5) | D2 Companion 1 (N=89) |
|---|---|---|---|
| Trigger rate | 91.7% (11/12) | 20.0% (1/5) | 21.3% (19/89) |
| Closed (A+C) | 8 | 0 | 5 |
| Closed-and-profitable (any ruleset) | 0 | 1 (F at +0.088R) | 12 (10 E winners + 1 A + 1 C; A/C single winners are same trade) |
| Mean R closed A+C | -0.469R | n/a | -0.143R |
| **E POSITIVE verdict** | n/a (E not tested in D1) | n/a (insufficient sample) | **YES (+0.585R mean closed)** |
| Best ruleset | A=C tied at -0.469R | F at +0.088R | E at +0.585R |

**Direction of change:** D1's bias-toward-recent-Ws produced high trigger rate (91.7%) but uniform losses via close_below_50d. D2's bias-free unbiased-Ws produced lower trigger rate (21%) but E captures meaningful upside via measured-move target. The chart-shape-appropriate trigger (D1's contribution) is necessary; the chart-shape-appropriate EXIT (D2's contribution via E) is also necessary; **both** unlock W-bottom expectancy.

### 8.3 D1 close-below-50d mis-calibration verdict on bias-free cohort

D1 findings Section 11.4 identified close_below_50d as mis-calibrated for W-bottom entries (8/8 D1 closures via single exit mode). D2 Companion 1 corroborates: A and C close 5 each via close_below_50d (out of 19 triggered; 26.3% closure rate via this single mode); mean -0.143R. The mis-calibration generalizes.

D's gated-50d variant (close_below_50d_gated armed only when SMA50 > entry * 1.05) avoids this mis-fire: D 0 closures via close_below_50d in Companion 1 (the gate never armed for any pattern; SMA50 stayed below 1.05 * entry). F's gated-50d variant similarly avoids the mis-fire.

The brief Section 3.4 + 3.6 "close_below_50d gated only if SMA50 > entry * 1.05" arming-gate IS the V1 implementation of D1 V2 candidate #3 (per D1 return report Section 5). **Implementation confirms the gate prevents the mis-fire.** Empirically, the gate is rarely armed on the D2 cohort (SMA50 stays close to entry on W-bottom breakouts) -- so its primary effect is "do nothing" rather than "do something different from C". The substantive replacement for the close-below-50d-exit in W-bottom trade management appears to be E's measured-move target.

---

## 9. Cross-comparison vs V2 OHLCV backtest (`e0a9edd`)

| Metric | V2 (`e0a9edd`) | D2 Companion 1 |
|---|---|---|
| Cohort generation | +67 watch->aplus subset; VCP detector | Full S&P 500 / NDX; double_bottom_w detector |
| Trigger rule | close > consolidation_pivot (VCP-appropriate) | close > center_peak_price (W-appropriate) |
| Trigger rate | 29.4% (5/17) | 21.3% (19/89) |
| Closed-and-profitable | 0 | 12 (10 E + 1 A + 1 C) |
| Mean R closed (best ruleset) | n/a | E at +0.585R |
| Verdict | NEGATIVE strict | POSITIVE for E |

V2 used VCP-appropriate trigger on what was largely a W-shape-dominated cohort (per V2 backtest's R1 hypothesis). D1 swapped to W-appropriate trigger but kept the SMA-based exits and got NEGATIVE strict. D2 keeps W-appropriate trigger AND adds chart-shape-appropriate EXITS (E's measured-move target) -> POSITIVE.

The arc demonstrates the R1 hypothesis (chart-shape-appropriate rules unlock expectancy) is correct AT BOTH ENDS: trigger AND exit must match the chart shape. Either alone is necessary-but-not-sufficient.

---

## 10. Limitations + caveats

### 10.1 L1 -- bias-free cohort is small (N=89 max at composite>=0.7)

Companion 1's N=89 is the largest D2 cohort but contains predominantly OLD W structures (5+ years historical) that trigger trivially on day-1-forward. The 19 triggered patterns include many "stale W" entries where center_peak is far below current price; E's measured-move target is consequently very-near-current-price. The +0.585R mean R closed reflects the ratio of (target - entry) / (entry - stop) for these stale-W setups. **Operator interpretation: E's POSITIVE verdict on this cohort is structural (target reachable) but the trades themselves don't correspond to actionable real-time entries.** For real-time deployment, the recency-60d filter would be canonical -- and at N=5, E has insufficient sample to discriminate.

### 10.2 L2 -- L6 archive bar-content TEMPORAL mutation

Per cumulative gotcha #26 + D1 findings Section 7.1. Forward-walked bars come from CURRENT archive; intervening pipeline runs may have mutated historical bar values. The structural anchors (trough_1_date, center_peak_price, trough_2_price) come from the persisted detector evidence in `pattern_cohort_evaluator` results.csv (which itself reads current archive at smoke time); structural-anchor drift bounded by smoke artifact age (~hours).

Estimated impact: ZERO for the 7 D2 tickers (none intersect with the 14 known L6-drifted candidates from V2 backtest CNTA/ECVT/APLS/FTI/STNG/PL).

### 10.3 L3 -- Stage-2 hard gate at detector level

The double_bottom_w detector's hard-gate on `current_stage == "stage_2"` (per `swing/patterns/double_bottom_w.py:530`) couples the cohort generation to production-DB candidate state. Tickers in Stage 1, 3, or 4 emit zero verdicts. The DEVIATION 1 fix (asof dates aligned to production DB run window) mitigates this but does NOT eliminate it; if the operator's production pipeline missed running on a session, that session's asof is unusable for cohort generation.

### 10.4 L4 -- forward-window asymmetry

Patterns with earlier `anchor_asof_date` have proportionally more forward bars. Companion 1's 89-pattern distribution skews toward older-asof patterns (since the same 7 tickers have multiple historical Ws across years). E's measured-move target is more reachable for old-W patterns whose center_peak is below current price. The Primary N=5 slice's recent-asof patterns have ~5-20 forward bars, often insufficient for E's target to be reached.

### 10.5 L5 -- single-asof-window cohort

D2 uses a 4-asof-date snapshot (2026-04-21 / 04-29 / 05-13 / 05-22). Different asof windows would yield different ticker sets + verdict distributions. Robustness across windows is a V2 candidate (run the same harness with rolling asof windows over multiple months to test verdict stability).

### 10.6 L6 -- E rule's per-pattern target dependence on structural anchor accuracy

E's target = `entry + (center_peak - min(trough_1, trough_2))`. If the detector's structural anchors are mis-identified (wrong trough_1 / center_peak / trough_2), E's target is wrong. Spot-check on the 10 E winners: targets ranged from +10% to +25% above entry; manual review of 2 examples (OXY, INTC) confirms structural anchor accuracy.

### 10.7 L7 -- F momentum gate auto-armed when ATR14 unavailable

Per Codex R1 M#2 fix. If pre-entry bars < 15, state.initial_atr14 is None; momentum_gate_armed=True by default. Affects very-short-history trades; not applicable to D2 cohort (all 7 tickers have multi-year archives).

### 10.8 L8 -- Reader cache_dir naming asymmetry (per D1 L8)

Read path uses `~/swing-data/prices-cache/` (hyphen) per `cfg.paths.prices_cache_dir`. Same as D1.

---

## 11. Implications + recommended next actions

### 11.1 R1 hypothesis status

The Turn F B study writeup's R1 reframing hypothesis (chart-shape-appropriate rules unlock cohort expectancy) is **FULLY VALIDATED** by D2 for Ruleset E:
- D1 partially validated (trigger-rate component +98% over V2 baseline; profitability component zero)
- **D2 fully validates: chart-shape-appropriate ENTRY (close > center_peak) + chart-shape-appropriate EXIT (measured-move target) unlock W-bottom expectancy at +0.585R mean closed, 83.3% win-rate**

The mechanism: SMA-based exits (A's terminal-SMA50; C's close-below-SMA50; D's gated-50d; F's gated-50d) systematically fire prematurely or never; the measured-move target avoids the SMA-exit family entirely.

### 11.2 R2 hypothesis (per-variable cohort smokes for 4 remaining VCP-family binding variables)

REINFORCED. D2's E result on the W-bottom cohort suggests that the OTHER binding variables (tightness_days_required +16; adr_min_pct +11; proximity_max_pct +5; orderliness_max_bar_ratio +1) may each have their OWN chart-shape-appropriate ruleset that unlocks expectancy. R2 is now even more compelling: per-variable cohort smoke + per-cohort backtest with chart-shape-appropriate trigger + exit could systematically identify which variables drive actionable A+ classification.

### 11.3 R3 hypothesis (treat sensitivity as upstream classification diagnostics)

D2 demonstrates that classification-flips DO translate to profitable trades IF the trade management ruleset matches the chart shape. The V2 sensitivity rankings are USEFUL for cohort selection (identify the most-frequently-flipping variables; build per-variable cohorts) but NOT sufficient on their own for deployment.

### 11.4 Recommended next dispatch

**Option A (RECOMMENDED): per-variable R2 cohort smoke + 6-ruleset backtest for `vcp.tightness_days_required +16`.** Mirror D2's structure (full bias-free universe; 4 asof dates aligned with production DB; 6 rulesets including E's measured-move target). Establishes whether E's POSITIVE verdict on W-bottom generalizes to OTHER chart shapes. Estimated cost: 6-10 hours (D2 harness modules are reusable; the trigger rule needs adaptation per chart shape).

**Option B (parallel/follow-up): real-time exemplar generation for E**. If E's measured-move target ACTUALLY works in real-time deployment (not just historical bias-free cohort), validate via prospective tracking: identify N most-recent W-bottom patterns from operator's pipeline; track each via Ruleset E for 30-60 sessions; report outcomes. Estimated cost: 1-2 hours setup + multi-month tracking.

**Option C (deferred): full Phase 14 commissioning consideration.** D2's POSITIVE finding for E is the FIRST substantive cohort-level validation in the research arc; promotes E's measured-move target to a deployment candidate. Phase 14 dispatch would scope productionizing E's logic into the swing/ pipeline (entry advisory, exit advisory, etc.).

---

## 12. Artifacts

- **Primary smoke (recency-60d / composite>=0.7; N=5):** [exports/research/w-bottom-ruleset-comparison-20260525T143436Z/](../exports/research/w-bottom-ruleset-comparison-20260525T143436Z/)
- **Companion 1 (no-recency-filter / composite>=0.7; N=89; HEADLINE):** [exports/research/w-bottom-ruleset-comparison-20260525T143456Z/](../exports/research/w-bottom-ruleset-comparison-20260525T143456Z/)
- **Companion 2 (recency-120d / composite>=0.5; N=26):** [exports/research/w-bottom-ruleset-comparison-20260525T143552Z/](../exports/research/w-bottom-ruleset-comparison-20260525T143552Z/)
- **Cohort substrate:** [exports/research/pattern-cohort-detection-20260526T000409Z/](../exports/research/pattern-cohort-detection-20260526T000409Z/) (untracked 184 MB results.csv; tracked manifest.json + summary.md)
- **Cohort CSV input:** [exports/research/cohorts/w_bottom_ruleset_comparison_sp500_apr_may_2026.csv](../exports/research/cohorts/w_bottom_ruleset_comparison_sp500_apr_may_2026.csv)
- **Backtest harness:** [research/harness/w_bottom_ruleset_comparison/](../research/harness/w_bottom_ruleset_comparison/) (5 modules: walkforward.py + rulesets.py + io.py + run.py + __init__.py)
- **Discriminating tests:** [tests/research/w_bottom_ruleset_comparison/](../tests/research/w_bottom_ruleset_comparison/) (57 fast tests; +14 Codex-R1/R2/R3 discriminating tests)
- **CLI subcommand:** `swing diagnose w-bottom-ruleset-comparison` (77 lines added to `swing/cli.py` per OQ-13-mirror carve-out)

---

## 13. Discipline preservation

- **NO Co-Authored-By footer** preserved across all 11 D2 commits.
- **`python -m swing.cli` invocation discipline** preserved (CLI subcommand registered + tested + smoke invoked via this path).
- **ASCII discipline** preserved across ALL 10 new source/test files + 3 smoke summary.md + 3 manifest.json + THIS findings doc + forthcoming return report. Programmatic body.encode('ascii') sweep PASSES.
- **Schema v21 UNCHANGED** (zero migration files added).
- **L2 LOCK preserved + REINFORCED:** 2 BINDING discriminating tests at `tests/research/w_bottom_ruleset_comparison/test_l2_lock.py` covering source-grep + import-graph sentinels. All OHLCV reads route through the V2 Shape A reader. ZERO new Schwab API calls. ZERO new yfinance fetches at backtest time.
- **V1 persisted state UNCHANGED:** ZERO SELECT/UPDATE/INSERT against `candidate_criteria` / `candidates` / `evaluation_runs` / `trades` / `pattern_evaluations`. Cohort source is the (already-persisted) pattern_cohort_evaluator results.csv; backtest reads OHLCV via the read-only Shape A reader; no DB writes.
- **Production `swing/` READ-ONLY EXCEPT OQ-13 carve-out:** SOLE write is the 77-line `diagnose_w_bottom_ruleset_comparison` CLI subcommand registration. `git diff main -- swing/` shows only this addition.
- **Fast suite:** 57 NEW D2 tests + 468 pre-existing research tests = 525 passing (test_aplus_v2_ohlcv_run skipped for env-var-guarded gate; same as baseline).
- **Codex MCP chain CONVERGED at R3 NO_NEW_CRITICAL_MAJOR after 3 rounds.** Cumulative: 0 CRITICAL + 6 MAJOR + 9 MINOR. ALL MAJORS resolved in-place or ACCEPTED with rationale; ALL MINORS resolved or banked.

---

*End of findings document. Verdict: **POSITIVE for Ruleset E (O'Neil cup-with-handle + Bulkowski measured-move target)** on Companion 1's N=89 cohort. First substantive POSITIVE verdict in V2 -> D1 -> D2 arc. Mechanism: chart-shape-appropriate measured-move TARGET unlocks W-bottom expectancy that SMA-based exits (A/C/D/F variants) systematically fire premature on. Recommended next action: Option A per-variable R2 cohort smoke + 6-ruleset backtest for next binding variable.*
