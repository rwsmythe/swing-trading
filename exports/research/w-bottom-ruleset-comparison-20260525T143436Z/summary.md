# W-Bottom Ruleset Comparison Backtest Summary

**Cohort:** composite>=0.7 double_bottom_w; recency<=60d (max_observed_asof) (5 unique W patterns)

**Cohort source:** exports\research\pattern-cohort-detection-20260526T000409Z\results.csv

**Recency filter:** trough_2 within 60 calendar days of max_observed_asof (5 of 89 verdicts passed).

**Both-exist diagnostic:** 0 ticker-reads hit Shape A + legacy (Shape A wins per OQ-18).

**Rulesets:** 6 (A_minervini_trail_ma + B_fixed_R_multiple + C_close_below_50d + D_minervini_stage2_progression + E_oneil_cup_with_handle_measured_move + F_qullamaggie_momentum_burst).

## Cross-ruleset comparison (ranked by expectancy_R_closed)

| Rank | Ruleset | Win-rate | Mean R closed | Std R closed | Mean R triggered | Max drawdown closed | Avg sessions closed |
|------|---------|----------|---------------|--------------|------------------|---------------------|---------------------|
| 1 | F_qullamaggie_momentum_burst | 100.0% | +0.088R | n/a | +0.088R | +0.274R | 5.0d |
| 2 | A_minervini_trail_ma | n/a | n/a | n/a | +0.348R | n/a | n/a |
| 3 | B_fixed_R_multiple | n/a | n/a | n/a | +0.348R | n/a | n/a |
| 4 | C_close_below_50d | n/a | n/a | n/a | +0.348R | n/a | n/a |
| 5 | D_minervini_stage2_progression | n/a | n/a | n/a | +0.348R | n/a | n/a |
| 6 | E_oneil_cup_with_handle_measured_move | n/a | n/a | n/a | +1.456R | n/a | n/a |

## Per-ruleset aggregate stats

| Ruleset | Patterns | Triggered | Closed | Winners | Losers | Untrig | Open | Win-rate | Avg R win | Avg R loser | Expectancy R closed | Avg sessions held (closed) | Avg sessions held (open) |
|---------|----------|-----------|--------|---------|--------|--------|------|----------|-----------|-------------|---------------------|------------------------|----------------------|
| A_minervini_trail_ma | 5 | 1 | 0 | 0 | 0 | 4 | 1 | n/a | n/a | n/a | n/a | n/a | 5.0d |
| B_fixed_R_multiple | 5 | 1 | 0 | 0 | 0 | 4 | 1 | n/a | n/a | n/a | n/a | n/a | 5.0d |
| C_close_below_50d | 5 | 1 | 0 | 0 | 0 | 4 | 1 | n/a | n/a | n/a | n/a | n/a | 5.0d |
| D_minervini_stage2_progression | 5 | 1 | 0 | 0 | 0 | 4 | 1 | n/a | n/a | n/a | n/a | n/a | 5.0d |
| E_oneil_cup_with_handle_measured_move | 5 | 1 | 0 | 0 | 0 | 4 | 1 | n/a | n/a | n/a | n/a | n/a | 5.0d |
| F_qullamaggie_momentum_burst | 5 | 1 | 1 | 1 | 0 | 4 | 0 | 100.0% | +0.088R | n/a | +0.088R | 5.0d | n/a |

## Exit-reason breakdown

| Ruleset | momentum_gate_fail | open_at_data_tail | untriggered |
|---------|--------------------|-------------------|-------------|
| A_minervini_trail_ma | 0 | 1 | 4 |
| B_fixed_R_multiple | 0 | 1 | 4 |
| C_close_below_50d | 0 | 1 | 4 |
| D_minervini_stage2_progression | 0 | 1 | 4 |
| E_oneil_cup_with_handle_measured_move | 0 | 1 | 4 |
| F_qullamaggie_momentum_burst | 1 | 0 | 4 |

## Per-composite-score-bucket analysis

| Bucket | Ruleset | Patterns | Triggered | Closed | Winners | Expectancy R closed |
|--------|---------|----------|-----------|--------|---------|---------------------|
| composite_0.7_to_0.9 | A_minervini_trail_ma | 3 | 1 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | B_fixed_R_multiple | 3 | 1 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | C_close_below_50d | 3 | 1 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | D_minervini_stage2_progression | 3 | 1 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | E_oneil_cup_with_handle_measured_move | 3 | 1 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | F_qullamaggie_momentum_burst | 3 | 1 | 1 | 1 | +0.088R |
| composite_0.9_plus | A_minervini_trail_ma | 2 | 0 | 0 | 0 | n/a |
| composite_0.9_plus | B_fixed_R_multiple | 2 | 0 | 0 | 0 | n/a |
| composite_0.9_plus | C_close_below_50d | 2 | 0 | 0 | 0 | n/a |
| composite_0.9_plus | D_minervini_stage2_progression | 2 | 0 | 0 | 0 | n/a |
| composite_0.9_plus | E_oneil_cup_with_handle_measured_move | 2 | 0 | 0 | 0 | n/a |
| composite_0.9_plus | F_qullamaggie_momentum_burst | 2 | 0 | 0 | 0 | n/a |

## Per-pattern detail (first 30 rows; sorted by ticker then trough_1_date)

| pattern_id | composite | days_t2_to_asof | ruleset | status | entry_date | exit_date | exit_reason | R-multiple | sessions_held | peak_R | dd_to_exit_R | pnl_$ |
|------------|-----------|-----------------|---------|--------|------------|-----------|-------------|------------|---------------|--------|--------------|-------|
| CNC-2026-03-13 | 0.727 | 53 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-03-13 | 0.727 | 53 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-03-13 | 0.727 | 53 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-03-13 | 0.727 | 53 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-03-13 | 0.727 | 53 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-03-13 | 0.727 | 53 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-02-23 | 0.764 | 44 | A_minervini_trail_ma | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.348R | 5 | +0.362R | +0.015R | $+13.04 |
| HPE-2026-02-23 | 0.764 | 44 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.348R | 5 | +0.362R | +0.015R | $+13.04 |
| HPE-2026-02-23 | 0.764 | 44 | C_close_below_50d | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.348R | 5 | +0.362R | +0.015R | $+13.04 |
| HPE-2026-02-23 | 0.764 | 44 | D_minervini_stage2_progression | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.348R | 5 | +0.362R | +0.015R | $+13.04 |
| HPE-2026-02-23 | 0.764 | 44 | E_oneil_cup_with_handle_measured_move | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +1.456R | 5 | +1.517R | +0.061R | $+54.59 |
| HPE-2026-02-23 | 0.764 | 44 | F_qullamaggie_momentum_burst | closed | 2026-05-15 | 2026-05-22 | momentum_gate_fail | +0.088R | 5 | +0.362R | +0.274R | $+3.29 |
| INTC-2026-03-03 | 0.933 | 53 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-03 | 0.933 | 53 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-03 | 0.933 | 53 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-03 | 0.933 | 53 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-03 | 0.933 | 53 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-03 | 0.933 | 53 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-03-06 | 0.834 | 53 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-03-06 | 0.834 | 53 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-03-06 | 0.834 | 53 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-03-06 | 0.834 | 53 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-03-06 | 0.834 | 53 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-03-06 | 0.834 | 53 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2026-04-17 | 0.933 | 14 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2026-04-17 | 0.933 | 14 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2026-04-17 | 0.933 | 14 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2026-04-17 | 0.933 | 14 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2026-04-17 | 0.933 | 14 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2026-04-17 | 0.933 | 14 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |

## Notes

- R-multiple = (exit_price - entry_price) / (entry_price - initial_stop).
- For scale-out trades (Ruleset F), r_multiple is the WEIGHTED final R:
  scale_fraction * scale_R + (1 - scale_fraction) * final_R.
- exit_reason `_after_scaleout` suffix indicates scale-out fired before final exit.
- Win-rate denominator = closed trades (excludes untriggered + open).
- Entry = next-session open after first close > center_peak_price.
- Initial stop varies per ruleset:
    - A/B/C/D/F: trough_2_price * 0.99 (canonical W right-shoulder buffer)
    - E: max(trough_2 * 0.99, entry * 0.92) (O'Neil 8% max loss floor)
- Trigger search window lower bound: STRICTLY AFTER max(trough_1_date, trough_2_date, effective_asof_date) where effective_asof = max(anchor_asof, max_observed_asof). Upper bound (INCLUSIVE): effective_asof + 60 business days.
- All non-momentum-gate exits CLOSE-based; momentum_gate_fail (F) is OPEN-based at session 6.
- OHLCV source: V2 Shape A reader at ~/swing-data/prices-cache/ (L2 LOCK preserved).
- L6 caveat: forward-walk bars come from CURRENT archive; may differ from V1 contemporaneous state.
