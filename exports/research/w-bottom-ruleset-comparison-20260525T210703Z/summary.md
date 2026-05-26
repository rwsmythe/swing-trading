# W-Bottom Ruleset Comparison Backtest Summary

**Cohort:** composite>=0.5 double_bottom_w; recency<=365d (max_observed_asof) (71 unique W patterns)

**Cohort source:** .worktrees\applied-research-w-bottom-ruleset-comparison\exports\research\pattern-cohort-detection-20260526T000409Z\results.csv

**Recency filter:** trough_2 within 365 calendar days of max_observed_asof (71 of 291 verdicts passed).

**Both-exist diagnostic:** 0 ticker-reads hit Shape A + legacy (Shape A wins per OQ-18).

**Rulesets:** 6 (A_minervini_trail_ma + B_fixed_R_multiple + C_close_below_50d + D_minervini_stage2_progression + E_oneil_cup_with_handle_measured_move + F_qullamaggie_momentum_burst).

## Cross-ruleset comparison (ranked by expectancy_R_closed)

| Rank | Ruleset | Win-rate | Mean R closed | Std R closed | Mean R triggered | Max drawdown closed | Avg sessions closed |
|------|---------|----------|---------------|--------------|------------------|---------------------|---------------------|
| 1 | D_minervini_stage2_progression | 100.0% | +1.685R | n/a | +0.393R | +0.947R | 16.0d |
| 2 | E_oneil_cup_with_handle_measured_move | 100.0% | +1.220R | 0.618R | +0.321R | +2.763R | 4.4d |
| 3 | A_minervini_trail_ma | 66.7% | +0.026R | 0.046R | +0.474R | +0.184R | 3.0d |
| 4 | C_close_below_50d | 66.7% | +0.026R | 0.046R | +0.474R | +0.184R | 3.0d |
| 5 | F_qullamaggie_momentum_burst | 0.0% | -0.228R | 0.074R | +0.434R | +0.347R | 5.0d |
| 6 | B_fixed_R_multiple | n/a | n/a | n/a | +0.426R | n/a | n/a |

## Per-ruleset aggregate stats

| Ruleset | Patterns | Triggered | Closed | Winners | Losers | Untrig | Open | Win-rate | Avg R win | Avg R loser | Expectancy R closed | Avg sessions held (closed) | Avg sessions held (open) |
|---------|----------|-----------|--------|---------|--------|--------|------|----------|-----------|-------------|---------------------|------------------------|----------------------|
| A_minervini_trail_ma | 71 | 13 | 9 | 6 | 3 | 58 | 4 | 66.7% | +0.056R | -0.035R | +0.026R | 3.0d | 18.0d |
| B_fixed_R_multiple | 71 | 13 | 0 | 0 | 0 | 58 | 13 | n/a | n/a | n/a | n/a | n/a | 9.0d |
| C_close_below_50d | 71 | 13 | 9 | 6 | 3 | 58 | 4 | 66.7% | +0.056R | -0.035R | +0.026R | 3.0d | 18.0d |
| D_minervini_stage2_progression | 71 | 13 | 1 | 1 | 0 | 58 | 12 | 100.0% | +1.685R | n/a | +1.685R | 16.0d | 8.0d |
| E_oneil_cup_with_handle_measured_move | 71 | 13 | 5 | 5 | 0 | 58 | 8 | 100.0% | +1.220R | n/a | +1.220R | 4.4d | 5.0d |
| F_qullamaggie_momentum_burst | 71 | 13 | 3 | 0 | 3 | 58 | 10 | 0.0% | n/a | -0.228R | -0.228R | 5.0d | 10.2d |

## Exit-reason breakdown

| Ruleset | close_below_50d | momentum_gate_fail | open_at_data_tail | open_at_data_tail_after_scaleout | target_measured_move | trail_stop | untriggered |
|---------|-----------------|--------------------|-------------------|----------------------------------|----------------------|------------|-------------|
| A_minervini_trail_ma | 9 | 0 | 4 | 0 | 0 | 0 | 58 |
| B_fixed_R_multiple | 0 | 0 | 13 | 0 | 0 | 0 | 58 |
| C_close_below_50d | 9 | 0 | 4 | 0 | 0 | 0 | 58 |
| D_minervini_stage2_progression | 0 | 0 | 12 | 0 | 0 | 1 | 58 |
| E_oneil_cup_with_handle_measured_move | 0 | 0 | 8 | 0 | 5 | 0 | 58 |
| F_qullamaggie_momentum_burst | 0 | 3 | 9 | 1 | 0 | 0 | 58 |

## Per-composite-score-bucket analysis

| Bucket | Ruleset | Patterns | Triggered | Closed | Winners | Expectancy R closed |
|--------|---------|----------|-----------|--------|---------|---------------------|
| composite_0.7_to_0.9 | A_minervini_trail_ma | 19 | 2 | 1 | 0 | -0.047R |
| composite_0.7_to_0.9 | B_fixed_R_multiple | 19 | 2 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | C_close_below_50d | 19 | 2 | 1 | 0 | -0.047R |
| composite_0.7_to_0.9 | D_minervini_stage2_progression | 19 | 2 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | E_oneil_cup_with_handle_measured_move | 19 | 2 | 1 | 1 | +0.853R |
| composite_0.7_to_0.9 | F_qullamaggie_momentum_burst | 19 | 2 | 1 | 0 | -0.303R |
| composite_0.9_plus | A_minervini_trail_ma | 3 | 0 | 0 | 0 | n/a |
| composite_0.9_plus | B_fixed_R_multiple | 3 | 0 | 0 | 0 | n/a |
| composite_0.9_plus | C_close_below_50d | 3 | 0 | 0 | 0 | n/a |
| composite_0.9_plus | D_minervini_stage2_progression | 3 | 0 | 0 | 0 | n/a |
| composite_0.9_plus | E_oneil_cup_with_handle_measured_move | 3 | 0 | 0 | 0 | n/a |
| composite_0.9_plus | F_qullamaggie_momentum_burst | 3 | 0 | 0 | 0 | n/a |
| composite_below_0.7 | A_minervini_trail_ma | 49 | 11 | 8 | 6 | +0.035R |
| composite_below_0.7 | B_fixed_R_multiple | 49 | 11 | 0 | 0 | n/a |
| composite_below_0.7 | C_close_below_50d | 49 | 11 | 8 | 6 | +0.035R |
| composite_below_0.7 | D_minervini_stage2_progression | 49 | 11 | 1 | 1 | +1.685R |
| composite_below_0.7 | E_oneil_cup_with_handle_measured_move | 49 | 11 | 4 | 4 | +1.312R |
| composite_below_0.7 | F_qullamaggie_momentum_burst | 49 | 11 | 2 | 0 | -0.190R |

## Per-pattern detail (first 400 rows; sorted by ticker then trough_1_date)

| pattern_id | composite | days_t2_to_asof | ruleset | status | entry_date | exit_date | exit_reason | R-multiple | sessions_held | peak_R | dd_to_exit_R | pnl_$ |
|------------|-----------|-----------------|---------|--------|------------|-----------|-------------|------------|---------------|--------|--------------|-------|
| CNC-2025-05-13 | 0.600 | 333 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-05-13 | 0.600 | 333 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-05-13 | 0.600 | 333 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-05-13 | 0.600 | 333 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-05-13 | 0.600 | 333 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-05-13 | 0.600 | 333 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-07-21 | 0.600 | 302 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-07-21 | 0.600 | 302 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-07-21 | 0.600 | 302 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-07-21 | 0.600 | 302 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-07-21 | 0.600 | 302 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-07-21 | 0.600 | 302 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-09-04 | 0.500 | 245 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-09-04 | 0.500 | 245 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-09-04 | 0.500 | 245 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-09-04 | 0.500 | 245 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-09-04 | 0.500 | 245 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-09-04 | 0.500 | 245 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-09-19 | 0.667 | 207 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-09-19 | 0.667 | 207 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-09-19 | 0.667 | 207 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-09-19 | 0.667 | 207 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-09-19 | 0.667 | 207 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-09-19 | 0.667 | 207 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-10-27 | 0.667 | 200 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-10-27 | 0.667 | 200 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-10-27 | 0.667 | 200 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-10-27 | 0.667 | 200 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-10-27 | 0.667 | 200 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-10-27 | 0.667 | 200 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-03 | 0.600 | 193 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-03 | 0.600 | 193 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-03 | 0.600 | 193 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-03 | 0.600 | 193 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-03 | 0.600 | 193 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-03 | 0.600 | 193 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-10 | 0.500 | 183 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-10 | 0.500 | 183 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-10 | 0.500 | 183 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-10 | 0.500 | 183 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-10 | 0.500 | 183 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-10 | 0.500 | 183 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-20 | 0.500 | 165 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-20 | 0.500 | 165 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-20 | 0.500 | 165 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-20 | 0.500 | 165 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-20 | 0.500 | 165 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-11-20 | 0.500 | 165 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-12-08 | 0.500 | 156 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-12-08 | 0.500 | 156 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-12-08 | 0.500 | 156 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-12-08 | 0.500 | 156 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-12-08 | 0.500 | 156 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-12-08 | 0.500 | 156 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-12-17 | 0.500 | 115 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-12-17 | 0.500 | 115 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-12-17 | 0.500 | 115 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-12-17 | 0.500 | 115 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-12-17 | 0.500 | 115 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2025-12-17 | 0.500 | 115 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-02-09 | 0.734 | 70 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-02-09 | 0.734 | 70 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-02-09 | 0.734 | 70 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-02-09 | 0.734 | 70 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-02-09 | 0.734 | 70 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-02-09 | 0.734 | 70 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-03-13 | 0.727 | 53 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-03-13 | 0.727 | 53 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-03-13 | 0.727 | 53 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-03-13 | 0.727 | 53 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-03-13 | 0.727 | 53 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2026-03-13 | 0.727 | 53 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-04-10 | 0.767 | 354 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-04-10 | 0.767 | 354 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-04-10 | 0.767 | 354 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-04-10 | 0.767 | 354 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-04-10 | 0.767 | 354 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-04-10 | 0.767 | 354 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-05-07 | 0.767 | 354 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-05-07 | 0.767 | 354 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-05-07 | 0.767 | 354 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-05-07 | 0.767 | 354 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-05-07 | 0.767 | 354 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-05-07 | 0.767 | 354 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-06-02 | 0.767 | 326 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-06-02 | 0.767 | 326 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-06-02 | 0.767 | 326 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-06-02 | 0.767 | 326 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-06-02 | 0.767 | 326 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-06-02 | 0.767 | 326 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-06-30 | 0.600 | 284 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-06-30 | 0.600 | 284 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-06-30 | 0.600 | 284 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-06-30 | 0.600 | 284 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-06-30 | 0.600 | 284 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-06-30 | 0.600 | 284 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-07-15 | 0.600 | 284 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-07-15 | 0.600 | 284 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-07-15 | 0.600 | 284 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-07-15 | 0.600 | 284 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-07-15 | 0.600 | 284 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-07-15 | 0.600 | 284 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-08-11 | 0.600 | 224 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-08-11 | 0.600 | 224 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-08-11 | 0.600 | 224 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-08-11 | 0.600 | 224 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-08-11 | 0.600 | 224 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-08-11 | 0.600 | 224 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-09-25 | 0.600 | 224 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-09-25 | 0.600 | 224 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-09-25 | 0.600 | 224 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-09-25 | 0.600 | 224 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-09-25 | 0.600 | 224 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-09-25 | 0.600 | 224 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-10-10 | 0.833 | 183 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-10-10 | 0.833 | 183 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-10-10 | 0.833 | 183 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-10-10 | 0.833 | 183 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-10-10 | 0.833 | 183 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-10-10 | 0.833 | 183 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-11-10 | 0.600 | 174 | A_minervini_trail_ma | closed | 2026-05-15 | 2026-05-18 | close_below_50d | -0.024R | 1 | +0.023R | +0.047R | $-0.90 |
| DOW-2025-11-10 | 0.600 | 174 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.164R | 5 | +0.023R | +0.186R | $-6.14 |
| DOW-2025-11-10 | 0.600 | 174 | C_close_below_50d | closed | 2026-05-15 | 2026-05-18 | close_below_50d | -0.024R | 1 | +0.023R | +0.047R | $-0.90 |
| DOW-2025-11-10 | 0.600 | 174 | D_minervini_stage2_progression | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.164R | 5 | +0.023R | +0.186R | $-6.14 |
| DOW-2025-11-10 | 0.600 | 174 | E_oneil_cup_with_handle_measured_move | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.958R | 5 | +0.133R | +1.091R | $-35.94 |
| DOW-2025-11-10 | 0.600 | 174 | F_qullamaggie_momentum_burst | closed | 2026-05-15 | 2026-05-22 | momentum_gate_fail | -0.156R | 5 | +0.023R | +0.179R | $-5.85 |
| DOW-2025-11-20 | 0.667 | 157 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-11-20 | 0.667 | 157 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-11-20 | 0.667 | 157 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-11-20 | 0.667 | 157 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-11-20 | 0.667 | 157 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-11-20 | 0.667 | 157 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-12-16 | 0.500 | 113 | A_minervini_trail_ma | closed | 2026-05-15 | 2026-05-18 | close_below_50d | -0.035R | 1 | +0.033R | +0.067R | $-1.30 |
| DOW-2025-12-16 | 0.500 | 113 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.236R | 5 | +0.033R | +0.268R | $-8.84 |
| DOW-2025-12-16 | 0.500 | 113 | C_close_below_50d | closed | 2026-05-15 | 2026-05-18 | close_below_50d | -0.035R | 1 | +0.033R | +0.067R | $-1.30 |
| DOW-2025-12-16 | 0.500 | 113 | D_minervini_stage2_progression | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.236R | 5 | +0.033R | +0.268R | $-8.84 |
| DOW-2025-12-16 | 0.500 | 113 | E_oneil_cup_with_handle_measured_move | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.958R | 5 | +0.133R | +1.091R | $-35.94 |
| DOW-2025-12-16 | 0.500 | 113 | F_qullamaggie_momentum_burst | closed | 2026-05-15 | 2026-05-22 | momentum_gate_fail | -0.225R | 5 | +0.033R | +0.257R | $-8.42 |
| DOW-2026-02-05 | 0.841 | 76 | A_minervini_trail_ma | closed | 2026-05-15 | 2026-05-18 | close_below_50d | -0.047R | 1 | +0.044R | +0.091R | $-1.76 |
| DOW-2026-02-05 | 0.841 | 76 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.318R | 5 | +0.044R | +0.362R | $-11.93 |
| DOW-2026-02-05 | 0.841 | 76 | C_close_below_50d | closed | 2026-05-15 | 2026-05-18 | close_below_50d | -0.047R | 1 | +0.044R | +0.091R | $-1.76 |
| DOW-2026-02-05 | 0.841 | 76 | D_minervini_stage2_progression | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.318R | 5 | +0.044R | +0.362R | $-11.93 |
| DOW-2026-02-05 | 0.841 | 76 | E_oneil_cup_with_handle_measured_move | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.958R | 5 | +0.133R | +1.091R | $-35.94 |
| DOW-2026-02-05 | 0.841 | 76 | F_qullamaggie_momentum_burst | closed | 2026-05-15 | 2026-05-22 | momentum_gate_fail | -0.303R | 5 | +0.044R | +0.347R | $-11.37 |
| DOW-2026-02-26 | 0.667 | 43 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2026-02-26 | 0.667 | 43 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2026-02-26 | 0.667 | 43 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2026-02-26 | 0.667 | 43 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2026-02-26 | 0.667 | 43 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2026-02-26 | 0.667 | 43 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2026-04-17 | 0.667 | 14 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2026-04-17 | 0.667 | 14 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2026-04-17 | 0.667 | 14 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2026-04-17 | 0.667 | 14 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2026-04-17 | 0.667 | 14 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2026-04-17 | 0.667 | 14 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-09-26 | 0.600 | 195 | A_minervini_trail_ma | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +1.321R | 15 | +1.346R | +0.025R | $+49.53 |
| HPE-2025-09-26 | 0.600 | 195 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +1.321R | 15 | +1.346R | +0.025R | $+49.53 |
| HPE-2025-09-26 | 0.600 | 195 | C_close_below_50d | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +1.321R | 15 | +1.346R | +0.025R | $+49.53 |
| HPE-2025-09-26 | 0.600 | 195 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +1.321R | 15 | +1.346R | +0.025R | $+49.53 |
| HPE-2025-09-26 | 0.600 | 195 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-14 | target_measured_move | +1.624R | 9 | +2.522R | +0.898R | $+60.89 |
| HPE-2025-09-26 | 0.600 | 195 | F_qullamaggie_momentum_burst | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +1.321R | 15 | +1.346R | +0.025R | $+49.53 |
| HPE-2025-10-16 | 0.767 | 183 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-10-16 | 0.767 | 183 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-10-16 | 0.767 | 183 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-10-16 | 0.767 | 183 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-10-16 | 0.767 | 183 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-10-16 | 0.767 | 183 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-11-20 | 0.667 | 122 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-11-20 | 0.667 | 122 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-11-20 | 0.667 | 122 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-11-20 | 0.667 | 122 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-11-20 | 0.667 | 122 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-11-20 | 0.667 | 122 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-01-20 | 0.941 | 88 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-01-20 | 0.941 | 88 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-01-20 | 0.941 | 88 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-01-20 | 0.941 | 88 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-01-20 | 0.941 | 88 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-01-20 | 0.941 | 88 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-02-23 | 0.764 | 53 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-02-23 | 0.764 | 53 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-02-23 | 0.764 | 53 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-02-23 | 0.764 | 53 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-02-23 | 0.764 | 53 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-02-23 | 0.764 | 53 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-03-10 | 0.500 | 30 | A_minervini_trail_ma | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +1.343R | 15 | +1.368R | +0.025R | $+50.36 |
| HPE-2026-03-10 | 0.500 | 30 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +1.343R | 15 | +1.368R | +0.025R | $+50.36 |
| HPE-2026-03-10 | 0.500 | 30 | C_close_below_50d | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +1.343R | 15 | +1.368R | +0.025R | $+50.36 |
| HPE-2026-03-10 | 0.500 | 30 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +1.343R | 15 | +1.368R | +0.025R | $+50.36 |
| HPE-2026-03-10 | 0.500 | 30 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-14 | target_measured_move | +2.026R | 9 | +2.522R | +0.496R | $+75.99 |
| HPE-2026-03-10 | 0.500 | 30 | F_qullamaggie_momentum_burst | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +1.343R | 15 | +1.368R | +0.025R | $+50.36 |
| INTC-2025-04-21 | 0.667 | 357 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-04-21 | 0.667 | 357 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-04-21 | 0.667 | 357 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-04-21 | 0.667 | 357 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-04-21 | 0.667 | 357 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-04-21 | 0.667 | 357 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-05-30 | 0.600 | 294 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-05-30 | 0.600 | 294 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-05-30 | 0.600 | 294 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-05-30 | 0.600 | 294 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-05-30 | 0.600 | 294 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-05-30 | 0.600 | 294 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-06-13 | 0.767 | 263 | A_minervini_trail_ma | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.144R | 21 | +1.419R | +0.275R | $+42.89 |
| INTC-2025-06-13 | 0.767 | 263 | B_fixed_R_multiple | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.144R | 21 | +1.419R | +0.275R | $+42.89 |
| INTC-2025-06-13 | 0.767 | 263 | C_close_below_50d | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.144R | 21 | +1.419R | +0.275R | $+42.89 |
| INTC-2025-06-13 | 0.767 | 263 | D_minervini_stage2_progression | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.144R | 21 | +1.419R | +0.275R | $+42.89 |
| INTC-2025-06-13 | 0.767 | 263 | E_oneil_cup_with_handle_measured_move | closed | 2026-04-23 | 2026-04-24 | target_measured_move | +0.853R | 1 | +3.616R | +2.763R | $+31.98 |
| INTC-2025-06-13 | 0.767 | 263 | F_qullamaggie_momentum_burst | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.144R | 21 | +1.419R | +0.275R | $+42.89 |
| INTC-2025-08-01 | 0.500 | 183 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-08-01 | 0.500 | 183 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-08-01 | 0.500 | 183 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-08-01 | 0.500 | 183 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-08-01 | 0.500 | 183 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-08-01 | 0.500 | 183 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-11-20 | 0.667 | 156 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-11-20 | 0.667 | 156 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-11-20 | 0.667 | 156 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-11-20 | 0.667 | 156 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-11-20 | 0.667 | 156 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-11-20 | 0.667 | 156 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-12-17 | 0.500 | 116 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-12-17 | 0.500 | 116 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-12-17 | 0.500 | 116 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-12-17 | 0.500 | 116 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-12-17 | 0.500 | 116 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-12-17 | 0.500 | 116 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-01-26 | 0.876 | 80 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-01-26 | 0.876 | 80 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-01-26 | 0.876 | 80 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-01-26 | 0.876 | 80 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-01-26 | 0.876 | 80 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-01-26 | 0.876 | 80 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-03 | 0.933 | 53 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-03 | 0.933 | 53 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-03 | 0.933 | 53 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-03 | 0.933 | 53 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-03 | 0.933 | 53 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-03 | 0.933 | 53 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-20 | 0.600 | 22 | A_minervini_trail_ma | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +2.122R | 21 | +2.632R | +0.510R | $+79.59 |
| INTC-2026-03-20 | 0.600 | 22 | B_fixed_R_multiple | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +2.122R | 21 | +2.632R | +0.510R | $+79.59 |
| INTC-2026-03-20 | 0.600 | 22 | C_close_below_50d | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +2.122R | 21 | +2.632R | +0.510R | $+79.59 |
| INTC-2026-03-20 | 0.600 | 22 | D_minervini_stage2_progression | closed | 2026-04-23 | 2026-05-15 | trail_stop | +1.685R | 16 | +2.632R | +0.947R | $+63.19 |
| INTC-2026-03-20 | 0.600 | 22 | E_oneil_cup_with_handle_measured_move | closed | 2026-04-23 | 2026-04-24 | target_measured_move | +1.133R | 1 | +3.616R | +2.483R | $+42.48 |
| INTC-2026-03-20 | 0.600 | 22 | F_qullamaggie_momentum_burst | open | 2026-04-23 | 2026-05-22 | open_at_data_tail_after_scaleout | +2.189R | 21 | +2.632R | +0.443R | $+82.09 |
| INTC-2026-03-30 | 0.500 | 4 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-30 | 0.500 | 4 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-30 | 0.500 | 4 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-30 | 0.500 | 4 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-30 | 0.500 | 4 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2026-03-30 | 0.500 | 4 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-04-16 | 0.667 | 364 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-04-16 | 0.667 | 364 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-04-16 | 0.667 | 364 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-04-16 | 0.667 | 364 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-04-16 | 0.667 | 364 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-04-16 | 0.667 | 364 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-08-11 | 0.767 | 224 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-08-11 | 0.767 | 224 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-08-11 | 0.767 | 224 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-08-11 | 0.767 | 224 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-08-11 | 0.767 | 224 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-08-11 | 0.767 | 224 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-10-10 | 0.600 | 183 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-10-10 | 0.600 | 183 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-10-10 | 0.600 | 183 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-10-10 | 0.600 | 183 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-10-10 | 0.600 | 183 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-10-10 | 0.600 | 183 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-11-20 | 0.667 | 142 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-11-20 | 0.667 | 142 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-11-20 | 0.667 | 142 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-11-20 | 0.667 | 142 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-11-20 | 0.667 | 142 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-11-20 | 0.667 | 142 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-12-31 | 0.500 | 102 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-12-31 | 0.500 | 102 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-12-31 | 0.500 | 102 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-12-31 | 0.500 | 102 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-12-31 | 0.500 | 102 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-12-31 | 0.500 | 102 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2026-02-09 | 0.628 | 53 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2026-02-09 | 0.628 | 53 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2026-02-09 | 0.628 | 53 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2026-02-09 | 0.628 | 53 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2026-02-09 | 0.628 | 53 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2026-02-09 | 0.628 | 53 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2026-03-30 | 0.667 | 24 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2026-03-30 | 0.667 | 24 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2026-03-30 | 0.667 | 24 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2026-03-30 | 0.667 | 24 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2026-03-30 | 0.667 | 24 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2026-03-30 | 0.667 | 24 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-05-05 | 0.500 | 364 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-05-05 | 0.500 | 364 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-05-05 | 0.500 | 364 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-05-05 | 0.500 | 364 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-05-05 | 0.500 | 364 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-05-05 | 0.500 | 364 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-08-06 | 0.667 | 261 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-08-06 | 0.667 | 261 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-08-06 | 0.667 | 261 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-08-06 | 0.667 | 261 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-08-06 | 0.667 | 261 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-08-06 | 0.667 | 261 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-09-03 | 0.767 | 224 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-09-03 | 0.767 | 224 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-09-03 | 0.767 | 224 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-09-03 | 0.767 | 224 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-09-03 | 0.767 | 224 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-09-03 | 0.767 | 224 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-10-10 | 0.767 | 183 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-10-10 | 0.767 | 183 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-10-10 | 0.767 | 183 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-10-10 | 0.767 | 183 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-10-10 | 0.767 | 183 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-10-10 | 0.767 | 183 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-11-20 | 0.500 | 108 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-11-20 | 0.500 | 108 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-11-20 | 0.500 | 108 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-11-20 | 0.500 | 108 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-11-20 | 0.500 | 108 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2025-11-20 | 0.500 | 108 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-02-03 | 0.839 | 77 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-02-03 | 0.839 | 77 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-02-03 | 0.839 | 77 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-02-03 | 0.839 | 77 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-02-03 | 0.839 | 77 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-02-03 | 0.839 | 77 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-03-06 | 0.834 | 53 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-03-06 | 0.834 | 53 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-03-06 | 0.834 | 53 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-03-06 | 0.834 | 53 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-03-06 | 0.834 | 53 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2026-03-06 | 0.834 | 53 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-05-05 | 0.667 | 348 | A_minervini_trail_ma | closed | 2026-05-15 | 2026-05-21 | close_below_50d | +0.051R | 4 | +0.186R | +0.135R | $+1.92 |
| OXY-2025-05-05 | 0.667 | 348 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.050R | 5 | +0.186R | +0.136R | $+1.88 |
| OXY-2025-05-05 | 0.667 | 348 | C_close_below_50d | closed | 2026-05-15 | 2026-05-21 | close_below_50d | +0.051R | 4 | +0.186R | +0.135R | $+1.92 |
| OXY-2025-05-05 | 0.667 | 348 | D_minervini_stage2_progression | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.050R | 5 | +0.186R | +0.136R | $+1.88 |
| OXY-2025-05-05 | 0.667 | 348 | E_oneil_cup_with_handle_measured_move | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.190R | 5 | +0.705R | +0.515R | $+7.12 |
| OXY-2025-05-05 | 0.667 | 348 | F_qullamaggie_momentum_burst | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.050R | 5 | +0.186R | +0.136R | $+1.88 |
| OXY-2025-05-30 | 0.667 | 326 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-05-30 | 0.667 | 326 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-05-30 | 0.667 | 326 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-05-30 | 0.667 | 326 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-05-30 | 0.667 | 326 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-05-30 | 0.667 | 326 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-06-30 | 0.667 | 310 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-06-30 | 0.667 | 310 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-06-30 | 0.667 | 310 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-06-30 | 0.667 | 310 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-06-30 | 0.667 | 310 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-06-30 | 0.667 | 310 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-07-16 | 0.767 | 289 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-07-16 | 0.767 | 289 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-07-16 | 0.767 | 289 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-07-16 | 0.767 | 289 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-07-16 | 0.767 | 289 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-07-16 | 0.767 | 289 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-08-06 | 0.500 | 255 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-08-06 | 0.500 | 255 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-08-06 | 0.500 | 255 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-08-06 | 0.500 | 255 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-08-06 | 0.500 | 255 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-08-06 | 0.500 | 255 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-09-09 | 0.667 | 242 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-09-09 | 0.667 | 242 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-09-09 | 0.667 | 242 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-09-09 | 0.667 | 242 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-09-09 | 0.667 | 242 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-09-09 | 0.667 | 242 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-09-22 | 0.600 | 208 | A_minervini_trail_ma | closed | 2026-05-15 | 2026-05-21 | close_below_50d | +0.052R | 4 | +0.187R | +0.136R | $+1.94 |
| OXY-2025-09-22 | 0.600 | 208 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.050R | 5 | +0.187R | +0.137R | $+1.89 |
| OXY-2025-09-22 | 0.600 | 208 | C_close_below_50d | closed | 2026-05-15 | 2026-05-21 | close_below_50d | +0.052R | 4 | +0.187R | +0.136R | $+1.94 |
| OXY-2025-09-22 | 0.600 | 208 | D_minervini_stage2_progression | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.050R | 5 | +0.187R | +0.137R | $+1.89 |
| OXY-2025-09-22 | 0.600 | 208 | E_oneil_cup_with_handle_measured_move | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.190R | 5 | +0.705R | +0.515R | $+7.12 |
| OXY-2025-09-22 | 0.600 | 208 | F_qullamaggie_momentum_burst | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.050R | 5 | +0.187R | +0.137R | $+1.89 |
| OXY-2025-10-17 | 0.767 | 198 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-10-17 | 0.767 | 198 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-10-17 | 0.767 | 198 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-10-17 | 0.767 | 198 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-10-17 | 0.767 | 198 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-10-17 | 0.767 | 198 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-11-05 | 0.767 | 157 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-11-05 | 0.767 | 157 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-11-05 | 0.767 | 157 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-11-05 | 0.767 | 157 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-11-05 | 0.767 | 157 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-11-05 | 0.767 | 157 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2025-11-20 | 0.600 | 148 | A_minervini_trail_ma | closed | 2026-05-15 | 2026-05-21 | close_below_50d | +0.046R | 4 | +0.168R | +0.122R | $+1.74 |
| OXY-2025-11-20 | 0.600 | 148 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.045R | 5 | +0.168R | +0.123R | $+1.70 |
| OXY-2025-11-20 | 0.600 | 148 | C_close_below_50d | closed | 2026-05-15 | 2026-05-21 | close_below_50d | +0.046R | 4 | +0.168R | +0.122R | $+1.74 |
| OXY-2025-11-20 | 0.600 | 148 | D_minervini_stage2_progression | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.045R | 5 | +0.168R | +0.123R | $+1.70 |
| OXY-2025-11-20 | 0.600 | 148 | E_oneil_cup_with_handle_measured_move | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.190R | 5 | +0.705R | +0.515R | $+7.12 |
| OXY-2025-11-20 | 0.600 | 148 | F_qullamaggie_momentum_burst | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.045R | 5 | +0.168R | +0.123R | $+1.70 |
| OXY-2025-12-16 | 0.500 | 113 | A_minervini_trail_ma | closed | 2026-05-15 | 2026-05-21 | close_below_50d | +0.056R | 4 | +0.203R | +0.147R | $+2.09 |
| OXY-2025-12-16 | 0.500 | 113 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.055R | 5 | +0.203R | +0.148R | $+2.05 |
| OXY-2025-12-16 | 0.500 | 113 | C_close_below_50d | closed | 2026-05-15 | 2026-05-21 | close_below_50d | +0.056R | 4 | +0.203R | +0.147R | $+2.09 |
| OXY-2025-12-16 | 0.500 | 113 | D_minervini_stage2_progression | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.055R | 5 | +0.203R | +0.148R | $+2.05 |

_(per-pattern detail truncated at 400 rows; see results.csv for full table)_

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
