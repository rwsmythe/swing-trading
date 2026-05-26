# W-Bottom Ruleset Comparison Backtest Summary

**Cohort:** composite>=0.7 double_bottom_w; NO RECENCY FILTER (all unique W primaries) (89 unique W patterns)

**Cohort source:** exports\research\pattern-cohort-detection-20260526T000409Z\results.csv

**Recency filter:** trough_2 within 60 calendar days of max_observed_asof (89 of 89 verdicts passed).

**Both-exist diagnostic:** 0 ticker-reads hit Shape A + legacy (Shape A wins per OQ-18).

**Rulesets:** 6 (A_minervini_trail_ma + B_fixed_R_multiple + C_close_below_50d + D_minervini_stage2_progression + E_oneil_cup_with_handle_measured_move + F_qullamaggie_momentum_burst).

## Cross-ruleset comparison (ranked by expectancy_R_closed)

| Rank | Ruleset | Win-rate | Mean R closed | Std R closed | Mean R triggered | Max drawdown closed | Avg sessions closed |
|------|---------|----------|---------------|--------------|------------------|---------------------|---------------------|
| 1 | E_oneil_cup_with_handle_measured_move | 83.3% | +0.585R | 0.888R | +0.455R | +2.890R | 3.7d |
| 2 | F_qullamaggie_momentum_burst | 28.6% | -0.121R | 0.149R | +0.378R | +0.347R | 5.0d |
| 3 | A_minervini_trail_ma | 20.0% | -0.143R | 0.174R | +0.428R | +0.474R | 2.8d |
| 4 | C_close_below_50d | 20.0% | -0.143R | 0.174R | +0.428R | +0.474R | 2.8d |
| 5 | B_fixed_R_multiple | n/a | n/a | n/a | +0.405R | n/a | n/a |
| 6 | D_minervini_stage2_progression | n/a | n/a | n/a | +0.405R | n/a | n/a |

## Per-ruleset aggregate stats

| Ruleset | Patterns | Triggered | Closed | Winners | Losers | Untrig | Open | Win-rate | Avg R win | Avg R loser | Expectancy R closed | Avg sessions held (closed) | Avg sessions held (open) |
|---------|----------|-----------|--------|---------|--------|--------|------|----------|-----------|-------------|---------------------|------------------------|----------------------|
| A_minervini_trail_ma | 89 | 19 | 5 | 1 | 4 | 70 | 14 | 20.0% | +0.102R | -0.205R | -0.143R | 2.8d | 13.4d |
| B_fixed_R_multiple | 89 | 19 | 0 | 0 | 0 | 70 | 19 | n/a | n/a | n/a | n/a | n/a | 12.1d |
| C_close_below_50d | 89 | 19 | 5 | 1 | 4 | 70 | 14 | 20.0% | +0.102R | -0.205R | -0.143R | 2.8d | 13.4d |
| D_minervini_stage2_progression | 89 | 19 | 0 | 0 | 0 | 70 | 19 | n/a | n/a | n/a | n/a | n/a | 12.1d |
| E_oneil_cup_with_handle_measured_move | 89 | 19 | 12 | 10 | 2 | 70 | 7 | 83.3% | +0.924R | -1.105R | +0.585R | 3.7d | 4.6d |
| F_qullamaggie_momentum_burst | 89 | 19 | 7 | 2 | 5 | 70 | 12 | 28.6% | +0.081R | -0.202R | -0.121R | 5.0d | 14.6d |

## Exit-reason breakdown

| Ruleset | close_below_50d | momentum_gate_fail | open_at_data_tail | stop_hit | target_measured_move | untriggered |
|---------|-----------------|--------------------|-------------------|----------|----------------------|-------------|
| A_minervini_trail_ma | 5 | 0 | 14 | 0 | 0 | 70 |
| B_fixed_R_multiple | 0 | 0 | 19 | 0 | 0 | 70 |
| C_close_below_50d | 5 | 0 | 14 | 0 | 0 | 70 |
| D_minervini_stage2_progression | 0 | 0 | 19 | 0 | 0 | 70 |
| E_oneil_cup_with_handle_measured_move | 0 | 0 | 7 | 2 | 10 | 70 |
| F_qullamaggie_momentum_burst | 0 | 7 | 12 | 0 | 0 | 70 |

## Per-composite-score-bucket analysis

| Bucket | Ruleset | Patterns | Triggered | Closed | Winners | Expectancy R closed |
|--------|---------|----------|-----------|--------|---------|---------------------|
| composite_0.7_to_0.9 | A_minervini_trail_ma | 80 | 17 | 4 | 0 | -0.205R |
| composite_0.7_to_0.9 | B_fixed_R_multiple | 80 | 17 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | C_close_below_50d | 80 | 17 | 4 | 0 | -0.205R |
| composite_0.7_to_0.9 | D_minervini_stage2_progression | 80 | 17 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | E_oneil_cup_with_handle_measured_move | 80 | 17 | 12 | 10 | +0.585R |
| composite_0.7_to_0.9 | F_qullamaggie_momentum_burst | 80 | 17 | 6 | 1 | -0.154R |
| composite_0.9_plus | A_minervini_trail_ma | 9 | 2 | 1 | 1 | +0.102R |
| composite_0.9_plus | B_fixed_R_multiple | 9 | 2 | 0 | 0 | n/a |
| composite_0.9_plus | C_close_below_50d | 9 | 2 | 1 | 1 | +0.102R |
| composite_0.9_plus | D_minervini_stage2_progression | 9 | 2 | 0 | 0 | n/a |
| composite_0.9_plus | E_oneil_cup_with_handle_measured_move | 9 | 2 | 0 | 0 | n/a |
| composite_0.9_plus | F_qullamaggie_momentum_burst | 9 | 2 | 1 | 1 | +0.074R |

## Per-pattern detail (first 400 rows; sorted by ticker then trough_1_date)

| pattern_id | composite | days_t2_to_asof | ruleset | status | entry_date | exit_date | exit_reason | R-multiple | sessions_held | peak_R | dd_to_exit_R | pnl_$ |
|------------|-----------|-----------------|---------|--------|------------|-----------|-------------|------------|---------------|--------|--------------|-------|
| CNC-2022-01-06 | 0.767 | 1577 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-01-06 | 0.767 | 1577 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-01-06 | 0.767 | 1577 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-01-06 | 0.767 | 1577 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-01-06 | 0.767 | 1577 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-01-06 | 0.767 | 1577 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-03-23 | 0.767 | 1481 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-03-23 | 0.767 | 1481 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-03-23 | 0.767 | 1481 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-03-23 | 0.767 | 1481 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-03-23 | 0.767 | 1481 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-03-23 | 0.767 | 1481 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-05-09 | 0.767 | 1439 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-05-09 | 0.767 | 1439 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-05-09 | 0.767 | 1439 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-05-09 | 0.767 | 1439 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-05-09 | 0.767 | 1439 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-05-09 | 0.767 | 1439 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-09-27 | 0.767 | 1320 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-09-27 | 0.767 | 1320 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-09-27 | 0.767 | 1320 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-09-27 | 0.767 | 1320 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-09-27 | 0.767 | 1320 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2022-09-27 | 0.767 | 1320 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-07-01 | 0.767 | 668 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-07-01 | 0.767 | 668 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-07-01 | 0.767 | 668 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-07-01 | 0.767 | 668 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-07-01 | 0.767 | 668 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-07-01 | 0.767 | 668 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-10-29 | 0.767 | 553 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-10-29 | 0.767 | 553 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-10-29 | 0.767 | 553 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-10-29 | 0.767 | 553 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-10-29 | 0.767 | 553 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-10-29 | 0.767 | 553 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-11-15 | 0.767 | 528 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-11-15 | 0.767 | 528 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-11-15 | 0.767 | 528 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-11-15 | 0.767 | 528 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-11-15 | 0.767 | 528 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| CNC-2024-11-15 | 0.767 | 528 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
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
| DOW-2021-10-13 | 0.767 | 1657 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2021-10-13 | 0.767 | 1657 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2021-10-13 | 0.767 | 1657 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2021-10-13 | 0.767 | 1657 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2021-10-13 | 0.767 | 1657 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2021-10-13 | 0.767 | 1657 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2022-07-14 | 0.767 | 1345 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2022-07-14 | 0.767 | 1345 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2022-07-14 | 0.767 | 1345 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2022-07-14 | 0.767 | 1345 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2022-07-14 | 0.767 | 1345 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2022-07-14 | 0.767 | 1345 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2023-03-17 | 0.767 | 1087 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2023-03-17 | 0.767 | 1087 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2023-03-17 | 0.767 | 1087 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2023-03-17 | 0.767 | 1087 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2023-03-17 | 0.767 | 1087 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2023-03-17 | 0.767 | 1087 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2023-05-31 | 0.833 | 1064 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2023-05-31 | 0.833 | 1064 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2023-05-31 | 0.833 | 1064 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2023-05-31 | 0.833 | 1064 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2023-05-31 | 0.833 | 1064 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2023-05-31 | 0.833 | 1064 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2024-08-05 | 0.767 | 607 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2024-08-05 | 0.767 | 607 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2024-08-05 | 0.767 | 607 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2024-08-05 | 0.767 | 607 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2024-08-05 | 0.767 | 607 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2024-08-05 | 0.767 | 607 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-01-10 | 0.767 | 473 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-01-10 | 0.767 | 473 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-01-10 | 0.767 | 473 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-01-10 | 0.767 | 473 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-01-10 | 0.767 | 473 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-01-10 | 0.767 | 473 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-02-03 | 0.767 | 444 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-02-03 | 0.767 | 444 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-02-03 | 0.767 | 444 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-02-03 | 0.767 | 444 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-02-03 | 0.767 | 444 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-02-03 | 0.767 | 444 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DOW-2025-04-10 | 0.767 | 331 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.258R | 4 | +0.038R | +0.297R | $-9.69 |
| DOW-2025-04-10 | 0.767 | 331 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.352R | 15 | +0.038R | +0.390R | $-13.19 |
| DOW-2025-04-10 | 0.767 | 331 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.258R | 4 | +0.038R | +0.297R | $-9.69 |
| DOW-2025-04-10 | 0.767 | 331 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.352R | 15 | +0.038R | +0.390R | $-13.19 |
| DOW-2025-04-10 | 0.767 | 331 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-07 | stop_hit | -1.105R | 4 | +0.163R | +1.269R | $-41.45 |
| DOW-2025-04-10 | 0.767 | 331 | F_qullamaggie_momentum_burst | closed | 2026-05-01 | 2026-05-08 | momentum_gate_fail | -0.245R | 5 | +0.038R | +0.283R | $-9.18 |
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
| DOW-2025-10-10 | 0.833 | 160 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.179R | 4 | +0.026R | +0.206R | $-6.72 |
| DOW-2025-10-10 | 0.833 | 160 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.244R | 15 | +0.026R | +0.271R | $-9.15 |
| DOW-2025-10-10 | 0.833 | 160 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.179R | 4 | +0.026R | +0.206R | $-6.72 |
| DOW-2025-10-10 | 0.833 | 160 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.244R | 15 | +0.026R | +0.271R | $-9.15 |
| DOW-2025-10-10 | 0.833 | 160 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-07 | stop_hit | -1.105R | 4 | +0.163R | +1.269R | $-41.45 |
| DOW-2025-10-10 | 0.833 | 160 | F_qullamaggie_momentum_burst | closed | 2026-05-01 | 2026-05-08 | momentum_gate_fail | -0.170R | 5 | +0.026R | +0.196R | $-6.37 |
| DOW-2026-02-05 | 0.841 | 76 | A_minervini_trail_ma | closed | 2026-05-15 | 2026-05-18 | close_below_50d | -0.047R | 1 | +0.044R | +0.091R | $-1.76 |
| DOW-2026-02-05 | 0.841 | 76 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.318R | 5 | +0.044R | +0.362R | $-11.93 |
| DOW-2026-02-05 | 0.841 | 76 | C_close_below_50d | closed | 2026-05-15 | 2026-05-18 | close_below_50d | -0.047R | 1 | +0.044R | +0.091R | $-1.76 |
| DOW-2026-02-05 | 0.841 | 76 | D_minervini_stage2_progression | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.318R | 5 | +0.044R | +0.362R | $-11.93 |
| DOW-2026-02-05 | 0.841 | 76 | E_oneil_cup_with_handle_measured_move | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.958R | 5 | +0.133R | +1.091R | $-35.94 |
| DOW-2026-02-05 | 0.841 | 76 | F_qullamaggie_momentum_burst | closed | 2026-05-15 | 2026-05-22 | momentum_gate_fail | -0.303R | 5 | +0.044R | +0.347R | $-11.37 |
| HPE-2021-10-27 | 0.767 | 1610 | A_minervini_trail_ma | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.588R | 15 | +0.600R | +0.011R | $+22.07 |
| HPE-2021-10-27 | 0.767 | 1610 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.588R | 15 | +0.600R | +0.011R | $+22.07 |
| HPE-2021-10-27 | 0.767 | 1610 | C_close_below_50d | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.588R | 15 | +0.600R | +0.011R | $+22.07 |
| HPE-2021-10-27 | 0.767 | 1610 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.588R | 15 | +0.600R | +0.011R | $+22.07 |
| HPE-2021-10-27 | 0.767 | 1610 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-08 | target_measured_move | +0.749R | 5 | +1.074R | +0.325R | $+28.09 |
| HPE-2021-10-27 | 0.767 | 1610 | F_qullamaggie_momentum_burst | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.588R | 15 | +0.600R | +0.011R | $+22.07 |
| HPE-2022-01-27 | 0.767 | 1543 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-01-27 | 0.767 | 1543 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-01-27 | 0.767 | 1543 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-01-27 | 0.767 | 1543 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-01-27 | 0.767 | 1543 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-01-27 | 0.767 | 1543 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-03-07 | 0.767 | 1499 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-03-07 | 0.767 | 1499 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-03-07 | 0.767 | 1499 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-03-07 | 0.767 | 1499 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-03-07 | 0.767 | 1499 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-03-07 | 0.767 | 1499 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-04-14 | 0.767 | 1487 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-04-14 | 0.767 | 1487 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-04-14 | 0.767 | 1487 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-04-14 | 0.767 | 1487 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-04-14 | 0.767 | 1487 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-04-14 | 0.767 | 1487 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2022-05-20 | 0.767 | 1413 | A_minervini_trail_ma | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.556R | 15 | +0.567R | +0.011R | $+20.87 |
| HPE-2022-05-20 | 0.767 | 1413 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.556R | 15 | +0.567R | +0.011R | $+20.87 |
| HPE-2022-05-20 | 0.767 | 1413 | C_close_below_50d | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.556R | 15 | +0.567R | +0.011R | $+20.87 |
| HPE-2022-05-20 | 0.767 | 1413 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.556R | 15 | +0.567R | +0.011R | $+20.87 |
| HPE-2022-05-20 | 0.767 | 1413 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-08 | target_measured_move | +1.056R | 5 | +1.074R | +0.017R | $+39.62 |
| HPE-2022-05-20 | 0.767 | 1413 | F_qullamaggie_momentum_burst | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.556R | 15 | +0.567R | +0.011R | $+20.87 |
| HPE-2022-06-16 | 0.767 | 1393 | A_minervini_trail_ma | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.537R | 15 | +0.547R | +0.010R | $+20.13 |
| HPE-2022-06-16 | 0.767 | 1393 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.537R | 15 | +0.547R | +0.010R | $+20.13 |
| HPE-2022-06-16 | 0.767 | 1393 | C_close_below_50d | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.537R | 15 | +0.547R | +0.010R | $+20.13 |
| HPE-2022-06-16 | 0.767 | 1393 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.537R | 15 | +0.547R | +0.010R | $+20.13 |
| HPE-2022-06-16 | 0.767 | 1393 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-06 | target_measured_move | +0.589R | 3 | +0.671R | +0.082R | $+22.08 |
| HPE-2022-06-16 | 0.767 | 1393 | F_qullamaggie_momentum_burst | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.537R | 15 | +0.547R | +0.010R | $+20.13 |
| HPE-2023-03-15 | 0.767 | 1107 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2023-03-15 | 0.767 | 1107 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2023-03-15 | 0.767 | 1107 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2023-03-15 | 0.767 | 1107 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2023-03-15 | 0.767 | 1107 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2023-03-15 | 0.767 | 1107 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2023-10-26 | 0.833 | 906 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2023-10-26 | 0.833 | 906 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2023-10-26 | 0.833 | 906 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2023-10-26 | 0.833 | 906 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2023-10-26 | 0.833 | 906 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2023-10-26 | 0.833 | 906 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2024-01-18 | 0.767 | 791 | A_minervini_trail_ma | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.615R | 15 | +0.627R | +0.012R | $+23.07 |
| HPE-2024-01-18 | 0.767 | 791 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.615R | 15 | +0.627R | +0.012R | $+23.07 |
| HPE-2024-01-18 | 0.767 | 791 | C_close_below_50d | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.615R | 15 | +0.627R | +0.012R | $+23.07 |
| HPE-2024-01-18 | 0.767 | 791 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.615R | 15 | +0.627R | +0.012R | $+23.07 |
| HPE-2024-01-18 | 0.767 | 791 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-05 | target_measured_move | +0.459R | 2 | +0.554R | +0.095R | $+17.21 |
| HPE-2024-01-18 | 0.767 | 791 | F_qullamaggie_momentum_burst | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.615R | 15 | +0.627R | +0.012R | $+23.07 |
| HPE-2024-03-15 | 0.767 | 751 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2024-03-15 | 0.767 | 751 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2024-03-15 | 0.767 | 751 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2024-03-15 | 0.767 | 751 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2024-03-15 | 0.767 | 751 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2024-03-15 | 0.767 | 751 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2024-08-07 | 0.933 | 619 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2024-08-07 | 0.933 | 619 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2024-08-07 | 0.933 | 619 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2024-08-07 | 0.933 | 619 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2024-08-07 | 0.933 | 619 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2024-08-07 | 0.933 | 619 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2024-11-27 | 0.767 | 497 | A_minervini_trail_ma | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +1.026R | 15 | +1.046R | +0.019R | $+38.49 |
| HPE-2024-11-27 | 0.767 | 497 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +1.026R | 15 | +1.046R | +0.019R | $+38.49 |
| HPE-2024-11-27 | 0.767 | 497 | C_close_below_50d | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +1.026R | 15 | +1.046R | +0.019R | $+38.49 |
| HPE-2024-11-27 | 0.767 | 497 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +1.026R | 15 | +1.046R | +0.019R | $+38.49 |
| HPE-2024-11-27 | 0.767 | 497 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-14 | target_measured_move | +1.455R | 9 | +2.522R | +1.067R | $+54.55 |
| HPE-2024-11-27 | 0.767 | 497 | F_qullamaggie_momentum_burst | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +1.026R | 15 | +1.046R | +0.019R | $+38.49 |
| HPE-2024-12-18 | 0.933 | 464 | A_minervini_trail_ma | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.292R | 5 | +0.305R | +0.012R | $+10.97 |
| HPE-2024-12-18 | 0.933 | 464 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.292R | 5 | +0.305R | +0.012R | $+10.97 |
| HPE-2024-12-18 | 0.933 | 464 | C_close_below_50d | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.292R | 5 | +0.305R | +0.012R | $+10.97 |
| HPE-2024-12-18 | 0.933 | 464 | D_minervini_stage2_progression | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.292R | 5 | +0.305R | +0.012R | $+10.97 |
| HPE-2024-12-18 | 0.933 | 464 | E_oneil_cup_with_handle_measured_move | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +1.456R | 5 | +1.517R | +0.061R | $+54.59 |
| HPE-2024-12-18 | 0.933 | 464 | F_qullamaggie_momentum_burst | closed | 2026-05-15 | 2026-05-22 | momentum_gate_fail | +0.074R | 5 | +0.305R | +0.231R | $+2.77 |
| HPE-2025-10-16 | 0.767 | 183 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-10-16 | 0.767 | 183 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-10-16 | 0.767 | 183 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-10-16 | 0.767 | 183 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-10-16 | 0.767 | 183 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2025-10-16 | 0.767 | 183 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-01-20 | 0.941 | 88 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-01-20 | 0.941 | 88 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-01-20 | 0.941 | 88 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-01-20 | 0.941 | 88 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-01-20 | 0.941 | 88 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-01-20 | 0.941 | 88 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| HPE-2026-02-23 | 0.764 | 44 | A_minervini_trail_ma | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.348R | 5 | +0.362R | +0.015R | $+13.04 |
| HPE-2026-02-23 | 0.764 | 44 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.348R | 5 | +0.362R | +0.015R | $+13.04 |
| HPE-2026-02-23 | 0.764 | 44 | C_close_below_50d | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.348R | 5 | +0.362R | +0.015R | $+13.04 |
| HPE-2026-02-23 | 0.764 | 44 | D_minervini_stage2_progression | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.348R | 5 | +0.362R | +0.015R | $+13.04 |
| HPE-2026-02-23 | 0.764 | 44 | E_oneil_cup_with_handle_measured_move | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +1.456R | 5 | +1.517R | +0.061R | $+54.59 |
| HPE-2026-02-23 | 0.764 | 44 | F_qullamaggie_momentum_burst | closed | 2026-05-15 | 2026-05-22 | momentum_gate_fail | +0.088R | 5 | +0.362R | +0.274R | $+3.29 |
| INTC-2022-02-23 | 0.767 | 1507 | A_minervini_trail_ma | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.541R | 15 | +0.803R | +0.262R | $+20.29 |
| INTC-2022-02-23 | 0.767 | 1507 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.541R | 15 | +0.803R | +0.262R | $+20.29 |
| INTC-2022-02-23 | 0.767 | 1507 | C_close_below_50d | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.541R | 15 | +0.803R | +0.262R | $+20.29 |
| INTC-2022-02-23 | 0.767 | 1507 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.541R | 15 | +0.803R | +0.262R | $+20.29 |
| INTC-2022-02-23 | 0.767 | 1507 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-01 | target_measured_move | +0.600R | 0 | +0.972R | +0.373R | $+22.48 |
| INTC-2022-02-23 | 0.767 | 1507 | F_qullamaggie_momentum_burst | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.541R | 15 | +0.803R | +0.262R | $+20.29 |
| INTC-2022-12-28 | 0.767 | 1180 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2022-12-28 | 0.767 | 1180 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2022-12-28 | 0.767 | 1180 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2022-12-28 | 0.767 | 1180 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2022-12-28 | 0.767 | 1180 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2022-12-28 | 0.767 | 1180 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2023-04-25 | 0.767 | 1062 | A_minervini_trail_ma | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.379R | 21 | +1.710R | +0.331R | $+51.71 |
| INTC-2023-04-25 | 0.767 | 1062 | B_fixed_R_multiple | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.379R | 21 | +1.710R | +0.331R | $+51.71 |
| INTC-2023-04-25 | 0.767 | 1062 | C_close_below_50d | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.379R | 21 | +1.710R | +0.331R | $+51.71 |
| INTC-2023-04-25 | 0.767 | 1062 | D_minervini_stage2_progression | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.379R | 21 | +1.710R | +0.331R | $+51.71 |
| INTC-2023-04-25 | 0.767 | 1062 | E_oneil_cup_with_handle_measured_move | closed | 2026-04-23 | 2026-04-24 | target_measured_move | +0.726R | 1 | +3.616R | +2.890R | $+27.23 |
| INTC-2023-04-25 | 0.767 | 1062 | F_qullamaggie_momentum_burst | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.379R | 21 | +1.710R | +0.331R | $+51.71 |
| INTC-2023-09-26 | 0.767 | 908 | A_minervini_trail_ma | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.585R | 21 | +1.966R | +0.381R | $+59.44 |
| INTC-2023-09-26 | 0.767 | 908 | B_fixed_R_multiple | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.585R | 21 | +1.966R | +0.381R | $+59.44 |
| INTC-2023-09-26 | 0.767 | 908 | C_close_below_50d | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.585R | 21 | +1.966R | +0.381R | $+59.44 |
| INTC-2023-09-26 | 0.767 | 908 | D_minervini_stage2_progression | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.585R | 21 | +1.966R | +0.381R | $+59.44 |
| INTC-2023-09-26 | 0.767 | 908 | E_oneil_cup_with_handle_measured_move | closed | 2026-04-23 | 2026-04-24 | target_measured_move | +0.825R | 1 | +3.616R | +2.791R | $+30.92 |
| INTC-2023-09-26 | 0.767 | 908 | F_qullamaggie_momentum_burst | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.585R | 21 | +1.966R | +0.381R | $+59.44 |
| INTC-2024-08-07 | 0.767 | 623 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2024-08-07 | 0.767 | 623 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2024-08-07 | 0.767 | 623 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2024-08-07 | 0.767 | 623 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2024-08-07 | 0.767 | 623 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2024-08-07 | 0.767 | 623 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-03-11 | 0.767 | 409 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-03-11 | 0.767 | 409 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-03-11 | 0.767 | 409 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-03-11 | 0.767 | 409 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-03-11 | 0.767 | 409 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-03-11 | 0.767 | 409 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| INTC-2025-06-13 | 0.767 | 263 | A_minervini_trail_ma | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.144R | 21 | +1.419R | +0.275R | $+42.89 |
| INTC-2025-06-13 | 0.767 | 263 | B_fixed_R_multiple | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.144R | 21 | +1.419R | +0.275R | $+42.89 |
| INTC-2025-06-13 | 0.767 | 263 | C_close_below_50d | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.144R | 21 | +1.419R | +0.275R | $+42.89 |
| INTC-2025-06-13 | 0.767 | 263 | D_minervini_stage2_progression | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.144R | 21 | +1.419R | +0.275R | $+42.89 |
| INTC-2025-06-13 | 0.767 | 263 | E_oneil_cup_with_handle_measured_move | closed | 2026-04-23 | 2026-04-24 | target_measured_move | +0.853R | 1 | +3.616R | +2.763R | $+31.98 |
| INTC-2025-06-13 | 0.767 | 263 | F_qullamaggie_momentum_burst | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.144R | 21 | +1.419R | +0.275R | $+42.89 |
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
| MCHP-2022-03-07 | 0.933 | 1486 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-03-07 | 0.933 | 1486 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-03-07 | 0.933 | 1486 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-03-07 | 0.933 | 1486 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-03-07 | 0.933 | 1486 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-03-07 | 0.933 | 1486 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-04-27 | 0.767 | 1474 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-04-27 | 0.767 | 1474 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-04-27 | 0.767 | 1474 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-04-27 | 0.767 | 1474 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-04-27 | 0.767 | 1474 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-04-27 | 0.767 | 1474 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-09-30 | 0.767 | 1316 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-09-30 | 0.767 | 1316 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-09-30 | 0.767 | 1316 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-09-30 | 0.767 | 1316 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-09-30 | 0.767 | 1316 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-09-30 | 0.767 | 1316 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-10-14 | 0.833 | 1296 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-10-14 | 0.833 | 1296 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-10-14 | 0.833 | 1296 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-10-14 | 0.833 | 1296 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-10-14 | 0.833 | 1296 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2022-10-14 | 0.833 | 1296 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2023-04-27 | 0.767 | 926 | A_minervini_trail_ma | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.028R | 5 | +0.071R | +0.099R | $-1.04 |
| MCHP-2023-04-27 | 0.767 | 926 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.028R | 5 | +0.071R | +0.099R | $-1.04 |
| MCHP-2023-04-27 | 0.767 | 926 | C_close_below_50d | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.028R | 5 | +0.071R | +0.099R | $-1.04 |
| MCHP-2023-04-27 | 0.767 | 926 | D_minervini_stage2_progression | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.028R | 5 | +0.071R | +0.099R | $-1.04 |
| MCHP-2023-04-27 | 0.767 | 926 | E_oneil_cup_with_handle_measured_move | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.089R | 5 | +0.228R | +0.317R | $-3.34 |
| MCHP-2023-04-27 | 0.767 | 926 | F_qullamaggie_momentum_burst | closed | 2026-05-15 | 2026-05-22 | momentum_gate_fail | -0.142R | 5 | +0.071R | +0.213R | $-5.33 |
| MCHP-2024-01-17 | 0.767 | 828 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-01-17 | 0.767 | 828 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-01-17 | 0.767 | 828 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-01-17 | 0.767 | 828 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-01-17 | 0.767 | 828 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-01-17 | 0.767 | 828 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-03-26 | 0.767 | 763 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-03-26 | 0.767 | 763 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-03-26 | 0.767 | 763 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-03-26 | 0.767 | 763 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-03-26 | 0.767 | 763 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-03-26 | 0.767 | 763 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-06-20 | 0.767 | 644 | A_minervini_trail_ma | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.029R | 5 | +0.075R | +0.105R | $-1.10 |
| MCHP-2024-06-20 | 0.767 | 644 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.029R | 5 | +0.075R | +0.105R | $-1.10 |
| MCHP-2024-06-20 | 0.767 | 644 | C_close_below_50d | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.029R | 5 | +0.075R | +0.105R | $-1.10 |
| MCHP-2024-06-20 | 0.767 | 644 | D_minervini_stage2_progression | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.029R | 5 | +0.075R | +0.105R | $-1.10 |
| MCHP-2024-06-20 | 0.767 | 644 | E_oneil_cup_with_handle_measured_move | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.089R | 5 | +0.228R | +0.317R | $-3.34 |
| MCHP-2024-06-20 | 0.767 | 644 | F_qullamaggie_momentum_burst | closed | 2026-05-15 | 2026-05-22 | momentum_gate_fail | -0.150R | 5 | +0.075R | +0.226R | $-5.64 |
| MCHP-2024-12-05 | 0.767 | 497 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-12-05 | 0.767 | 497 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-12-05 | 0.767 | 497 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-12-05 | 0.767 | 497 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-12-05 | 0.767 | 497 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2024-12-05 | 0.767 | 497 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-08-11 | 0.767 | 224 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-08-11 | 0.767 | 224 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-08-11 | 0.767 | 224 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-08-11 | 0.767 | 224 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-08-11 | 0.767 | 224 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| MCHP-2025-08-11 | 0.767 | 224 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2021-06-18 | 0.767 | 1768 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2021-06-18 | 0.767 | 1768 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2021-06-18 | 0.767 | 1768 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2021-06-18 | 0.767 | 1768 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2021-06-18 | 0.767 | 1768 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2021-06-18 | 0.767 | 1768 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-03-14 | 0.767 | 1502 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-03-14 | 0.767 | 1502 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-03-14 | 0.767 | 1502 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-03-14 | 0.767 | 1502 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-03-14 | 0.767 | 1502 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-03-14 | 0.767 | 1502 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-04-11 | 0.767 | 1486 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-04-11 | 0.767 | 1486 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-04-11 | 0.767 | 1486 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-04-11 | 0.767 | 1486 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-04-11 | 0.767 | 1486 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-04-11 | 0.767 | 1486 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-04-27 | 0.767 | 1474 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-04-27 | 0.767 | 1474 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-04-27 | 0.767 | 1474 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-04-27 | 0.767 | 1474 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-04-27 | 0.767 | 1474 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-04-27 | 0.767 | 1474 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-05-09 | 0.767 | 1406 | A_minervini_trail_ma | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.301R | 15 | +0.358R | +0.057R | $+11.27 |
| ON-2022-05-09 | 0.767 | 1406 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.301R | 15 | +0.358R | +0.057R | $+11.27 |
| ON-2022-05-09 | 0.767 | 1406 | C_close_below_50d | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.301R | 15 | +0.358R | +0.057R | $+11.27 |
| ON-2022-05-09 | 0.767 | 1406 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.301R | 15 | +0.358R | +0.057R | $+11.27 |
| ON-2022-05-09 | 0.767 | 1406 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-14 | target_measured_move | +1.925R | 9 | +2.256R | +0.331R | $+72.20 |
| ON-2022-05-09 | 0.767 | 1406 | F_qullamaggie_momentum_burst | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | +0.301R | 15 | +0.358R | +0.057R | $+11.27 |
| ON-2022-10-14 | 0.833 | 1296 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-10-14 | 0.833 | 1296 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-10-14 | 0.833 | 1296 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-10-14 | 0.833 | 1296 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-10-14 | 0.833 | 1296 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2022-10-14 | 0.833 | 1296 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2023-02-24 | 0.767 | 1152 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2023-02-24 | 0.767 | 1152 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2023-02-24 | 0.767 | 1152 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2023-02-24 | 0.767 | 1152 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2023-02-24 | 0.767 | 1152 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2023-02-24 | 0.767 | 1152 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2023-08-24 | 1.000 | 960 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2023-08-24 | 1.000 | 960 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2023-08-24 | 1.000 | 960 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2023-08-24 | 1.000 | 960 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2023-08-24 | 1.000 | 960 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2023-08-24 | 1.000 | 960 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2024-06-20 | 0.767 | 666 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2024-06-20 | 0.767 | 666 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2024-06-20 | 0.767 | 666 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2024-06-20 | 0.767 | 666 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2024-06-20 | 0.767 | 666 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2024-06-20 | 0.767 | 666 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2024-07-25 | 0.767 | 653 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2024-07-25 | 0.767 | 653 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2024-07-25 | 0.767 | 653 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2024-07-25 | 0.767 | 653 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2024-07-25 | 0.767 | 653 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2024-07-25 | 0.767 | 653 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2024-08-07 | 0.833 | 623 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2024-08-07 | 0.833 | 623 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2024-08-07 | 0.833 | 623 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| ON-2024-08-07 | 0.833 | 623 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |

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
