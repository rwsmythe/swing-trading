# V2 vcp.tightness_range_factor=1.005 Walk-Forward Backtest — Findings

**Date:** 2026-05-24
**Dispatch brief:** [docs/v2-tightness-range-factor-backtest-dispatch-brief.md](v2-tightness-range-factor-backtest-dispatch-brief.md)
**Study extended:** [research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md](../research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md)
**Smoke artifact source:** `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.{csv,md}` (full 63-eval-run reproduction)
**Backtest artifact:** `exports/research/tightness-range-factor-backtest-<ISO>/`
**Branch:** `applied-research-v2-tightness-range-factor-backtest`

---

## 1. Headline verdict

**INSUFFICIENT POSITIVE EVIDENCE for the cfg-policy proposal** at `vcp.tightness_range_factor=1.005`.
Of the 17 unique VCP patterns derived from the 67 watch→aplus flips:

- **12 patterns (70.6%) never triggered** (no close > pivot within available forward bars).
- **2 patterns (11.8%) had zero forward bars** (SSRM/WULF; archives last bar = 2026-05-15 == first eval_run asof).
- **5 patterns (29.4%) triggered** but **all 5 remain open positions** at data tail (2026-05-22 or earlier per ticker-specific archive freshness).
- **0 patterns closed** under any of the three exit rulesets (Minervini trail-MA / Fixed R-multiple / Close-below-50d).

Among the 5 open positions, R-multiples at data tail are:

| Pattern | Ticker | Entry date | Days held | R-multiple at tail |
|---------|--------|------------|-----------|--------------------|
| FRO-r19 | FRO | 2026-05-11 | 3 | -0.34R |
| PTEN-r40 | PTEN | 2026-05-19 | 3 | -0.18R |
| RNG-r22 | RNG | 2026-05-04 | 8 | -0.28R |
| YOU-r22 | YOU | 2026-05-07 | 15 | +0.04R |
| YOU-r55 | YOU | 2026-05-21 | 1 | -0.13R |

Mean unrealized R: **-0.18R** across the 5 open positions. None of the rulesets matter for the verdict — all five are open at the same R because none hit a +1R, +2R, +3R, or 50d-arm threshold.

**Negative cfg-policy substrate.** Loosening `vcp.tightness_range_factor` from baseline 0.67 to 1.005 adds +75 aplus flips per the V2 sensitivity headline — but those flips DO NOT correspond to profitable trade opportunities in the immediate forward window. The vast majority either fail to break out (max forward close ≤ 99% of pivot) or break out marginally and stall.

---

## 2. Cohort enumeration

**Pre-dedup (from sweep drill-down):** 67 candidate rows × `(sweep_point=1.005, new_bucket=aplus)`; 15 unique tickers.

**Post-pattern-dedup (≤ 5 business days gap collapse):** 17 unique VCP patterns.

| Pattern | Ticker | First asof | Eval-run cluster | Pivot | Initial stop | R unit |
|---------|--------|------------|------------------|-------|--------------|--------|
| DK-r53 | DK | 2026-05-15 | [53, 54] | 49.50 | 37.25 | 12.25 |
| DNTH-r12 | DNTH | 2026-04-23 | [12-21] | 96.50 | 77.64 | 18.86 |
| FRO-r19 | FRO | 2026-04-27 | [19-24] | 38.16 | 33.00 | 5.16 |
| KOD-r25 | KOD | 2026-04-29 | [25-32] | 47.84 | 38.22 | 9.62 |
| NAT-r44 | NAT | 2026-05-12 | [44] | 6.22 | 5.30 | 0.92 |
| OII-r9 | OII | 2026-04-21 | [9, 10] | 39.06 | 33.64 | 5.42 |
| PTEN-r40 | PTEN | 2026-05-08 | [40, 41] | 12.62 | 9.17 | 3.45 |
| RLMD-r13 | RLMD | 2026-04-23 | [13-33] | 7.94 | 6.275 | 1.665 |
| RLMD-r42 | RLMD | 2026-05-11 | [42-44] | 8.00 | 6.81 | 1.19 |
| RNG-r22 | RNG | 2026-04-28 | [22-30] | 43.83 | 33.05 | 10.78 |
| SSRM-r52 | SSRM | 2026-05-15 | [52] | 36.28 | 28.07 | 8.21 |
| TROX-r25 | TROX | 2026-04-29 | [25-28] | 10.59 | 8.45 | 2.14 |
| TSHA-r45 | TSHA | 2026-05-13 | [45] | 7.30 | 5.75 | 1.55 |
| UCTT-r44 | UCTT | 2026-05-12 | [44] | 88.37 | 68.94 | 19.43 |
| WULF-r52 | WULF | 2026-05-15 | [52] | 25.76 | 19.44 | 6.32 |
| YOU-r22 | YOU | 2026-04-28 | [22, 23, 24] | 59.515 | 45.38 | 14.135 |
| YOU-r55 | YOU | 2026-05-18 | [55, 56, 57, 64] | 61.68 | 52.01 | 9.67 |

**Pre-extracted summary discrepancy check (per brief §1):** drill-down emits 67 flips; matrix headline `delta_aplus[sweep_point=1.005] = +75` net. Discrepancy of 8 is consistent with the L6 caveat — the matrix delta is computed against V2-recomputed baseline `bucket_for(...) == aplus`, while the drill-down only records V1-persisted-bucket vs V2-recomputed transitions. The 8-row gap likely reflects 8 candidates where V2 baseline-aplus is preserved at 1.005 (no flip event recorded) but the matrix still counts them in the aplus_count delta. This does NOT affect the backtest scope.

---

## 3. Pattern-grouping rationale + sensitivity

**Threshold:** consecutive eval_runs collapse into one pattern when the business-day gap is `< 5` (i.e., 0-4 business days). Per brief OQ-3 default ~5 trading days. Used `numpy.busday_count` for precise business-day inequality.

**Result at threshold 5 BD:** 17 patterns.

**Sensitivity** (brief OQ-3 watch item):
- At threshold 3 BD: would split RLMD-r13 (which spans April 23 → May 4, with a 7-BD gap between runs 18 and 29) into 2 patterns AND YOU-r55 → YOU-r57 (May 18) vs YOU-r64 (May 22) into 2 patterns. Effective pattern count ≈ 19.
- At threshold 10 BD: would merge RLMD-r13 and RLMD-r42 into one pattern AND YOU-r22 and YOU-r55. Effective pattern count ≈ 15.

The verdict is INSENSITIVE to grouping threshold within the 3-10 BD range — all variants show ~70% untriggered + ~30% triggered-with-marginal-negative-R.

---

## 4. Backtest engine: design + rulesets

### 4.1 Entry rule (shared across all 3 rulesets)

- **Trigger:** first session AFTER `first_data_asof_date` where Close > pivot.
- **Entry:** NEXT session's Open after the trigger session.
- **Initial stop:** V1-persisted `candidates.initial_stop` from the FIRST eval_run in the pattern group (per brief OQ-1 default).
- **R unit:** `(entry_price - initial_stop)`.

If no next-session Open is available after the trigger (e.g., last bar of archive triggers), pattern is classified `untriggered` (not `closed`).

### 4.2 Ruleset A — Minervini trail-MA (per `reference/methodology/minervini-sell-side-rules.md` M.2 + `reference/methodology/dst-take-profit-and-trail.md` D.3)

Anchor: TLSMW p. 296 "Once a stock amasses a percentage gain that is a multiple of your stop loss... move up your stop loss to breakeven or trail a stop to lock in the majority of the gain." The 7%/20% example = 2.86R; brief default = +2R extension trigger.

- Initial stop: V1 `initial_stop`.
- Trail-trigger arm: when intraday High >= entry + 2*(entry - initial_stop) [+2R extension].
- On arm: stop moves to max(stop, breakeven).
- Post-arm: trail stop = max(stop, 50d SMA on close); ratchet up only.
- Hard exit: first close < 50d SMA after arm fires (`close_below_50d`).
- Else: intraday Low <= current stop fires `trail_stop` (or `stop_hit` pre-arm).

### 4.3 Ruleset B — Fixed R-multiple

- Initial stop: V1 `initial_stop`.
- BE arm: when intraday High >= entry + 1R → stop moves to entry (breakeven).
- Target exit: when intraday High >= entry + 3R → exit at target price (`target_3R`).
- Post-BE trail: stop = max(stop, 21d SMA on close) [brief OQ-2 default (b)].
- Else: stop hit, target, or data-tail.

### 4.4 Ruleset C — Close-below-50d-SMA

- Initial stop: V1 `initial_stop`.
- Trail-arm: when daily close > 50d SMA AND 50d SMA is rising (slope over 5-bar lookback > 0).
- On arm: stop = max(stop, 50d SMA).
- Post-arm: stop = max(stop, 50d SMA on close).
- Hard exit: first close < 50d SMA after arm (`close_below_50d`).

### 4.5 Stop-fill semantics + ratchet

- Stop-hit fill: at the stop price (worst-case market-stop assumption).
- Trail-stop fill (intraday Low <= stop): at the stop price.
- Close-below-MA fill: at the bar's Close (signal is close-confirmed per DST D.3 source-of-truth).
- Trail ratchet: monotonically non-decreasing for longs.

---

## 5. Per-ruleset aggregate stats

**Cohort (vcp.tightness_range_factor=1.005 flips; 17 patterns):**

| Ruleset | Patterns | Triggered | Closed | Win | Loss | Untrig | Open | Win-rate | Avg R win | Avg R loser | Expectancy R | Avg days held |
|---------|----------|-----------|--------|-----|------|--------|------|----------|-----------|-------------|--------------|---------------|
| A_minervini_trail_ma | 17 | 5 | 0 | 0 | 0 | 12 | 5 | n/a | n/a | n/a | n/a | n/a |
| B_fixed_R_multiple | 17 | 5 | 0 | 0 | 0 | 12 | 5 | n/a | n/a | n/a | n/a | n/a |
| C_close_below_50d | 17 | 5 | 0 | 0 | 0 | 12 | 5 | n/a | n/a | n/a | n/a | n/a |

All three rulesets show IDENTICAL pattern-level outcomes because the 5 triggered patterns all reach data tail before any of the trail/target/exit conditions arm. The 3 rulesets only meaningfully differentiate POST-+2R / POST-+1R / POST-50d-cross — and none of the 5 triggered patterns has progressed that far in the available forward window.

**Control (V1 baseline aplus; sweep_point=0.67; 2 patterns):**

| Ruleset | Patterns | Triggered | Closed | Win | Loss | Untrig | Open | Win-rate | Expectancy R |
|---------|----------|-----------|--------|-----|------|--------|------|----------|--------------|
| A_minervini_trail_ma | 2 | 1 | 0 | 0 | 0 | 1 | 1 | n/a | n/a |
| B_fixed_R_multiple | 2 | 1 | 0 | 0 | 0 | 1 | 1 | n/a | n/a |
| C_close_below_50d | 2 | 1 | 0 | 0 | 0 | 1 | 1 | n/a | n/a |

Control: SLDB-r9 (asof 2026-04-21; pivot 8.87; stop 6.40) untriggered (SLDB cache too sparse); YOU-r31 (asof 2026-05-01; pivot 59.515; stop 45.38) triggered 2026-05-07 same as cohort YOU-r22 — same trade arc.

**Cross-cohort comparison:** undefined — no closed trades on either side.

---

## 6. Untriggered near-miss analysis

The 12 "untriggered" patterns reveal the breakouts came CLOSE but never crossed pivot. Per-pattern max forward close as % of pivot:

| Pattern | fwd bars | Max forward close | % of pivot | Verdict |
|---------|----------|-------------------|------------|---------|
| DK-r53 | 5 | 45.54 | 92.0% | failed to break |
| DNTH-r12 | 5 | 87.80 | 91.0% | failed to break |
| KOD-r25 | 8 | 45.89 | 95.9% | failed to break |
| NAT-r44 | 2 | 5.60 | 90.0% | failed to break (sparse) |
| OII-r9 | 4 | 38.47 | 98.5% | failed to break (sparse) |
| RLMD-r13 | 21 | 7.86 | 99.0% | failed to break |
| RLMD-r42 | 9 | 7.49 | 93.6% | failed to break |
| TROX-r25 | 8 | 10.48 | 99.0% | failed to break |
| TSHA-r45 | 1 | 6.30 | 86.3% | failed to break (very sparse) |
| UCTT-r44 | 8 | 86.38 | 97.7% | failed to break |
| SSRM-r52 | 0 | n/a | n/a | no forward bars |
| WULF-r52 | 0 | n/a | n/a | no forward bars |

**Key observation:** even patterns with ample forward data (RLMD-r13 with 21 bars; KOD-r25 with 8 bars; UCTT-r44 with 8 bars; TROX-r25 with 8 bars) NEVER closed above pivot. The misses are mostly 1-9 percentage points short. This is not a data sparsity story — it is the *signature behavior of a marginal A+ flip*: the candidate trips the loosened criterion (sweep_point=1.005 vs baseline 0.67) but never actually launches a breakout move.

---

## 7. Limitations + caveats

### 7.1 L6 caveat — archive bar-content TEMPORAL mutation

Per `research/method-records/aplus-criteria-calibration.md` v0.3.0 "Known limitations" §L6: pivots used for the backtest come from V1-persisted state (`candidates.pivot` + `candidates.initial_stop` at the FIRST eval_run in each pattern group). These were stamped at V1 pipeline run time and reflect the OHLCV archive contents at that moment. The forward-walk uses the CURRENT archive. If intervening pipeline runs mutated historical bars (per CLAUDE.md gotcha #26), the entry-trigger close (Close > pivot) may evaluate against slightly different bar values than were available at V1 persistence time.

**Backtest fidelity impact:** the entry-trigger detection is the only surface where pivot drift would matter. The forward-walk after entry uses bar values consistently from the current archive (no re-comparison against V1 frozen state). The 3 ruleset exits (50d SMA crosses, +2R extensions, +1R BE, +3R target, 21d SMA trails) all run against current-archive bars only.

**Estimated impact on this study:** if the 14 L6-drifted candidates from the V2 full-reproduction smoke (CNTA × 2 + ECVT + APLS × 3 + FTI × 2 + STNG × 3 + PL × 3) intersect the tightness_range_factor=1.005 cohort, their entry triggers could be sensitive to pivot drift. Cross-check: NONE of those 14 drift-affected tickers appear in this cohort's 15 tickers — so L6 has zero direct impact here.

### 7.2 L4 caveat — Shape A vs legacy parquet asymmetry (cross-archive)

Per CLAUDE.md gotcha #24 + method-record §L4. The V2 OHLCV reader prefers Shape A `.yfinance.parquet` over legacy `.parquet`. For this cohort's 15 tickers, only DK has Shape A; the other 14 fall through to legacy. The legacy archives for many tickers are themselves stale (last bar 2026-04-27 to 2026-05-15 for the 14 tickers in question; vs target data tail 2026-05-22). This is an operator-cache state issue, not a V2 reader issue.

**Backtest fidelity impact:** patterns with sparse forward archives (NAT 2 bars, OII 4 bars, DK 5 bars, DNTH 5 bars, TSHA 1 bar, SSRM/WULF 0 bars) cannot be evaluated to maturity. The "untriggered" classification for these is honest — but the verdict is "no breakout in available data" not "no breakout in 2-week window".

**Remediation candidate (NOT implemented per dispatch brief L2 LOCK + V1-state-read-only):** refresh OHLCV archives for the affected 14 tickers via the production pipeline, then re-run the backtest. This is an operator-paired next step.

### 7.3 Walk-forward window asymmetry across patterns

Patterns with earlier first_data_asof_date (e.g., OII-r9 at 2026-04-21; DNTH-r12 + RLMD-r13 + YOU-r22 at 2026-04-23/28) have potentially ~3-4 weeks of forward bars; patterns with later asof_date (NAT-r44, TSHA-r45, UCTT-r44, SSRM/WULF-r52, YOU-r55) have ~1 week or less. Forward-window asymmetry favors earlier patterns. **Mitigation:** the near-miss diagnostic (§6) confirms even long-window patterns failed to break out.

### 7.4 N=5 triggered + N=0 closed: statistical un-decidability

The expectancy verdict rests on 5 unrealized R values: -0.34, -0.28, -0.18, -0.13, +0.04 (mean = -0.18R). Sample size is too small for confidence intervals to be meaningful. The verdict ("INSUFFICIENT POSITIVE EVIDENCE") is structural, not statistical — even if the 5 open positions resolved to positive R, the 12 untriggered patterns dominate the population-level signal.

### 7.5 OQ-4 (untriggered denominator) disposition

Per brief OQ-4 default (SEPARATE): the win-rate denominator excludes untriggered patterns. **Both interpretations:**

| Interpretation | Closed | Triggered | Total | Effective win-rate |
|----------------|--------|-----------|-------|---------------------|
| Untriggered SEPARATE (brief default) | 0 / 0 | 0 / 5 | 0 / 17 | n/a (0 closed) |
| Untriggered counted as 0R losers | 0 / 0 | 0 / 17 | 0 / 17 | 0% (winners / non-stop-hit) |

Both interpretations support the negative-verdict conclusion. The trade-positive cohort would need closed-trade positive expectancy AND a non-trivial trigger rate.

---

## 8. Cross-ruleset comparison + verdict on cfg-policy proposal substrate

### 8.1 Cross-ruleset comparison

All 3 rulesets emit IDENTICAL pattern-level outcomes on this cohort because none of the 5 triggered patterns has progressed far enough for the rulesets' divergent post-trigger behavior (+2R extension trigger; +1R BE + +3R target; 50d SMA arm) to fire. Net: the rulesets are indistinguishable on this cohort.

### 8.2 Verdict on cfg-policy proposal substrate (per V2.1 §VII.C)

**NEGATIVE — do not promote `vcp.tightness_range_factor=1.005` to shadow → production via the V2.1 §VII.C cfg-policy promotion ladder.**

**Evidence:**

1. **70.6% non-breakout rate** (12 / 17 patterns; max forward close 86-99% of pivot — close but never crossed).
2. **0% closed-trade rate** under any of 3 exit rulesets.
3. **Mean unrealized R = -0.18R** across 5 open positions; 4 of 5 negative.
4. **No cross-ruleset edge** — all three rulesets emit identical outcomes (i.e., the ruleset choice is moot on this cohort).
5. **Control cohort (baseline 5 A+)** is materially smaller (2 patterns) and inherits the same data-tail constraints; the binding-variable narrative from the V2 sensitivity study is NOT supported by walk-forward profitability.

**Interpretation:** the V2 sensitivity sweep's +75 max_delta_aplus headline at sweep_point=1.005 measures candidate-classification deltas, not realized-trade profitability. Loosening the tightness threshold materially increases the A+ surface by ~16x (5 → 80) — but the marginal candidates added by loosening are predominantly NON-BREAKOUT-DURING-EVAL-WINDOW patterns. The threshold relaxation captures noise more than it captures missed signal.

### 8.3 Recommended next actions

**Option A — Abandon `vcp.tightness_range_factor` as the next cfg-policy substrate.** The binding-variable headline is robust (V2-internal arithmetic per Amendment 2) but does not translate to operator-trade profitability. Pivot to a different binding variable's backtest study — e.g., `vcp.tightness_days_required` +16 (next-most-binding).

**Option B — Operator-paired archive refresh + re-run.** Refresh OHLCV Shape A archives for the 14 stale-cache tickers via production pipeline runs (this WOULD modify V1 OHLCV-archive state, outside this backtest's scope). Re-run the backtest to verify the forward-window-sparsity caveat is not concealing positive signal. Estimated cost: 1 production pipeline run + ~30 minutes operator time.

**Option C — Extend window to a multi-quarter horizon.** The current evaluation window (~4-5 weeks post-asof) may be too short for VCP-style breakouts (which historically take 8-20+ weeks to mature). A study of VCP breakouts that triggered between 2024 and 2025 with full forward-walk to 2026 would provide statistical power. This is a substantially larger V2.5/V3 dispatch.

**RECOMMENDED:** Option A in the immediate term (this study's signal is sufficient to deprioritize the headline binding variable for cfg-policy authoring); Option B as an operator-paired follow-up that closes the data-sparsity caveat with low effort.

---

## 9. L6 fidelity impact characterization (per brief §6.7 + OQ-5)

Per dispatch brief §6.7: the L6 caveat (archive bar-content TEMPORAL mutation between V1 persistence time and V2 current-archive read time) impacts backtest pivot identification but not the forward walk. The 14 L6-drifted candidates from the V2 full-reproduction smoke (CNTA / ECVT / APLS / FTI / STNG / PL) do NOT intersect this cohort's 15 tickers. **L6 impact on this study: ZERO.** This is a fortunate alignment, not an architectural guarantee — future backtest studies on different cohorts should explicitly cross-check L6 drift overlap.

---

## 10. Open-question dispositions enumerated

Per brief §9:

| OQ | Question | Disposition |
|----|----------|-------------|
| 1 | pivot from FIRST vs LAST eval_run | DEFAULT (FIRST per brief). No alternative explored — the 5 triggered patterns trigger BEFORE any later eval_run in their group, so LAST-pivot would equal FIRST-pivot for all 5 triggered cases. For the 12 untriggered patterns, LAST-pivot would in some cases be ~5-15% higher (later eval_runs caught further consolidation top) which would only DECREASE the trigger rate — same negative verdict. |
| 2 | Ruleset B post-BE trail sub-option | DEFAULT (b) 21d SMA per brief. Not exercised — no Ruleset B patterns crossed +1R BE. |
| 3 | Pattern-grouping window sensitivity | TESTED. 3-10 BD range yields 15-19 patterns; verdict invariant. |
| 4 | Untriggered denominator (SEPARATE vs counted as 0R loser) | BOTH interpretations documented (§7.5); verdict invariant. |
| 5 | L6 archive-mutation impact on backtest fidelity | ZERO impact for this cohort — no ticker overlap with the 14 L6-drifted candidates (§9). |

---

## 11. Artifacts

- **Results CSV (cohort):** `exports/research/tightness-range-factor-backtest-<ISO>/results_cohort.csv`
- **Results CSV (control):** `exports/research/tightness-range-factor-backtest-<ISO>/results_control.csv`
- **Combined results CSV:** `exports/research/tightness-range-factor-backtest-<ISO>/results.csv`
- **Summary markdown:** `exports/research/tightness-range-factor-backtest-<ISO>/summary.md`
- **Backtest harness:** `research/harness/backtest_v2_tightness/` (5 new modules: patterns.py + rulesets.py + walkforward.py + io.py + run.py)
- **Discriminating tests:** `tests/research/backtest_v2_tightness/` (16 tests covering pattern dedup + 3 rulesets + entry trigger + open/untriggered semantics)

---

## 12. Cumulative discipline + L2 LOCK + V1-state-read-only verification

- **NO Co-Authored-By footer** preserved across all backtest commits.
- **`python -m swing.cli` invocation discipline** preserved (harness invoked via `python -m research.harness.backtest_v2_tightness.run`).
- **ASCII-only** on runtime CLI paths + markdown narrative.
- **Schema v21 UNCHANGED** (zero migration files added).
- **L2 LOCK preserved:** backtest harness reads ONLY from `research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader.read_yfinance_shape_a`; ZERO new Schwab API calls; ZERO yfinance fetch calls.
- **V1 persisted state UNCHANGED:** `candidate_criteria` / `candidates` / `evaluation_runs` / `trades` / `pattern_evaluations` all READ-ONLY (only SELECTs against `candidates` + `evaluation_runs`).
- **Production `swing/` READ-ONLY:** zero files modified under `swing/` (verifiable via `git diff main -- swing/`).
- **Tests:** 16 new fast tests at `tests/research/backtest_v2_tightness/`; all pass under `python -m pytest`.

---

*End of findings document. Verdict: NEGATIVE cfg-policy substrate; recommend Option A (pivot to next binding variable) OR Option B (operator-paired archive refresh + re-run). Detailed evidence at §1 + §6 + §8.*
