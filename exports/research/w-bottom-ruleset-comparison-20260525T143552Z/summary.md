# W-Bottom Ruleset Comparison Backtest Summary

**Cohort:** composite>=0.5 double_bottom_w; recency<=120d (max_observed_asof) (26 unique W patterns)

**Cohort source:** exports\research\pattern-cohort-detection-20260526T000409Z\results.csv

**Recency filter:** trough_2 within 120 calendar days of max_observed_asof (26 of 291 verdicts passed).

**Both-exist diagnostic:** 0 ticker-reads hit Shape A + legacy (Shape A wins per OQ-18).

**Rulesets:** 6 (A_minervini_trail_ma + B_fixed_R_multiple + C_close_below_50d + D_minervini_stage2_progression + E_oneil_cup_with_handle_measured_move + F_qullamaggie_momentum_burst).

## Cross-ruleset comparison (ranked by expectancy_R_closed)

| Rank | Ruleset | Win-rate | Mean R closed | Std R closed | Mean R triggered | Max drawdown closed | Avg sessions closed |
|------|---------|----------|---------------|--------------|------------------|---------------------|---------------------|
| 1 | D_minervini_stage2_progression | 100.0% | +1.685R | n/a | +0.380R | +0.947R | 16.0d |
| 2 | E_oneil_cup_with_handle_measured_move | 100.0% | +1.208R | 0.784R | +0.298R | +2.483R | 4.0d |
| 3 | A_minervini_trail_ma | 60.0% | +0.021R | 0.057R | +0.510R | +0.184R | 2.8d |
| 4 | C_close_below_50d | 60.0% | +0.021R | 0.057R | +0.510R | +0.184R | 2.8d |
| 5 | F_qullamaggie_momentum_burst | 0.0% | -0.264R | 0.056R | +0.455R | +0.347R | 5.0d |
| 6 | B_fixed_R_multiple | n/a | n/a | n/a | +0.442R | n/a | n/a |

## Per-ruleset aggregate stats

| Ruleset | Patterns | Triggered | Closed | Winners | Losers | Untrig | Open | Win-rate | Avg R win | Avg R loser | Expectancy R closed | Avg sessions held (closed) | Avg sessions held (open) |
|---------|----------|-----------|--------|---------|--------|--------|------|----------|-----------|-------------|---------------------|------------------------|----------------------|
| A_minervini_trail_ma | 26 | 7 | 5 | 3 | 2 | 19 | 2 | 60.0% | +0.062R | -0.041R | +0.021R | 2.8d | 18.0d |
| B_fixed_R_multiple | 26 | 7 | 0 | 0 | 0 | 19 | 7 | n/a | n/a | n/a | n/a | n/a | 8.7d |
| C_close_below_50d | 26 | 7 | 5 | 3 | 2 | 19 | 2 | 60.0% | +0.062R | -0.041R | +0.021R | 2.8d | 18.0d |
| D_minervini_stage2_progression | 26 | 7 | 1 | 1 | 0 | 19 | 6 | 100.0% | +1.685R | n/a | +1.685R | 16.0d | 6.7d |
| E_oneil_cup_with_handle_measured_move | 26 | 7 | 3 | 3 | 0 | 19 | 4 | 100.0% | +1.208R | n/a | +1.208R | 4.0d | 5.0d |
| F_qullamaggie_momentum_burst | 26 | 7 | 2 | 0 | 2 | 19 | 5 | 0.0% | n/a | -0.264R | -0.264R | 5.0d | 10.2d |

## Exit-reason breakdown

| Ruleset | close_below_50d | momentum_gate_fail | open_at_data_tail | open_at_data_tail_after_scaleout | target_measured_move | trail_stop | untriggered |
|---------|-----------------|--------------------|-------------------|----------------------------------|----------------------|------------|-------------|
| A_minervini_trail_ma | 5 | 0 | 2 | 0 | 0 | 0 | 19 |
| B_fixed_R_multiple | 0 | 0 | 7 | 0 | 0 | 0 | 19 |
| C_close_below_50d | 5 | 0 | 2 | 0 | 0 | 0 | 19 |
| D_minervini_stage2_progression | 0 | 0 | 6 | 0 | 0 | 1 | 19 |
| E_oneil_cup_with_handle_measured_move | 0 | 0 | 4 | 0 | 3 | 0 | 19 |
| F_qullamaggie_momentum_burst | 0 | 2 | 4 | 1 | 0 | 0 | 19 |

## Per-composite-score-bucket analysis

| Bucket | Ruleset | Patterns | Triggered | Closed | Winners | Expectancy R closed |
|--------|---------|----------|-----------|--------|---------|---------------------|
| composite_0.7_to_0.9 | A_minervini_trail_ma | 7 | 1 | 1 | 0 | -0.047R |
| composite_0.7_to_0.9 | B_fixed_R_multiple | 7 | 1 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | C_close_below_50d | 7 | 1 | 1 | 0 | -0.047R |
| composite_0.7_to_0.9 | D_minervini_stage2_progression | 7 | 1 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | E_oneil_cup_with_handle_measured_move | 7 | 1 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | F_qullamaggie_momentum_burst | 7 | 1 | 1 | 0 | -0.303R |
| composite_0.9_plus | A_minervini_trail_ma | 3 | 0 | 0 | 0 | n/a |
| composite_0.9_plus | B_fixed_R_multiple | 3 | 0 | 0 | 0 | n/a |
| composite_0.9_plus | C_close_below_50d | 3 | 0 | 0 | 0 | n/a |
| composite_0.9_plus | D_minervini_stage2_progression | 3 | 0 | 0 | 0 | n/a |
| composite_0.9_plus | E_oneil_cup_with_handle_measured_move | 3 | 0 | 0 | 0 | n/a |
| composite_0.9_plus | F_qullamaggie_momentum_burst | 3 | 0 | 0 | 0 | n/a |
| composite_below_0.7 | A_minervini_trail_ma | 16 | 6 | 4 | 3 | +0.038R |
| composite_below_0.7 | B_fixed_R_multiple | 16 | 6 | 0 | 0 | n/a |
| composite_below_0.7 | C_close_below_50d | 16 | 6 | 4 | 3 | +0.038R |
| composite_below_0.7 | D_minervini_stage2_progression | 16 | 6 | 1 | 1 | +1.685R |
| composite_below_0.7 | E_oneil_cup_with_handle_measured_move | 16 | 6 | 3 | 3 | +1.208R |
| composite_below_0.7 | F_qullamaggie_momentum_burst | 16 | 6 | 1 | 0 | -0.225R |

## Per-pattern detail (first 156 rows; sorted by ticker then trough_1_date)

| pattern_id | composite | days_t2_to_asof | ruleset | status | entry_date | exit_date | exit_reason | R-multiple | sessions_held | peak_R | dd_to_exit_R | pnl_$ |
|------------|-----------|-----------------|---------|--------|------------|-----------|-------------|------------|---------------|--------|--------------|-------|
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
| OXY-2025-12-16 | 0.500 | 113 | A_minervini_trail_ma | closed | 2026-05-15 | 2026-05-21 | close_below_50d | +0.056R | 4 | +0.203R | +0.147R | $+2.09 |
| OXY-2025-12-16 | 0.500 | 113 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.055R | 5 | +0.203R | +0.148R | $+2.05 |
| OXY-2025-12-16 | 0.500 | 113 | C_close_below_50d | closed | 2026-05-15 | 2026-05-21 | close_below_50d | +0.056R | 4 | +0.203R | +0.147R | $+2.09 |
| OXY-2025-12-16 | 0.500 | 113 | D_minervini_stage2_progression | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.055R | 5 | +0.203R | +0.148R | $+2.05 |
| OXY-2025-12-16 | 0.500 | 113 | E_oneil_cup_with_handle_measured_move | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.190R | 5 | +0.705R | +0.515R | $+7.12 |
| OXY-2025-12-16 | 0.500 | 113 | F_qullamaggie_momentum_burst | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.055R | 5 | +0.203R | +0.148R | $+2.05 |
| OXY-2026-01-20 | 0.652 | 100 | A_minervini_trail_ma | closed | 2026-05-15 | 2026-05-21 | close_below_50d | +0.062R | 4 | +0.224R | +0.162R | $+2.32 |
| OXY-2026-01-20 | 0.652 | 100 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.060R | 5 | +0.224R | +0.164R | $+2.27 |
| OXY-2026-01-20 | 0.652 | 100 | C_close_below_50d | closed | 2026-05-15 | 2026-05-21 | close_below_50d | +0.062R | 4 | +0.224R | +0.162R | $+2.32 |
| OXY-2026-01-20 | 0.652 | 100 | D_minervini_stage2_progression | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.060R | 5 | +0.224R | +0.164R | $+2.27 |
| OXY-2026-01-20 | 0.652 | 100 | E_oneil_cup_with_handle_measured_move | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.190R | 5 | +0.705R | +0.515R | $+7.12 |
| OXY-2026-01-20 | 0.652 | 100 | F_qullamaggie_momentum_burst | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.060R | 5 | +0.224R | +0.164R | $+2.27 |
| OXY-2026-02-05 | 0.652 | 90 | A_minervini_trail_ma | closed | 2026-05-15 | 2026-05-21 | close_below_50d | +0.070R | 4 | +0.253R | +0.184R | $+2.62 |
| OXY-2026-02-05 | 0.652 | 90 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.068R | 5 | +0.253R | +0.185R | $+2.56 |
| OXY-2026-02-05 | 0.652 | 90 | C_close_below_50d | closed | 2026-05-15 | 2026-05-21 | close_below_50d | +0.070R | 4 | +0.253R | +0.184R | $+2.62 |
| OXY-2026-02-05 | 0.652 | 90 | D_minervini_stage2_progression | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.068R | 5 | +0.253R | +0.185R | $+2.56 |
| OXY-2026-02-05 | 0.652 | 90 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-15 | 2026-05-19 | target_measured_move | +0.464R | 2 | +0.649R | +0.186R | $+17.40 |
| OXY-2026-02-05 | 0.652 | 90 | F_qullamaggie_momentum_burst | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | +0.068R | 5 | +0.253R | +0.185R | $+2.56 |
| OXY-2026-03-10 | 0.667 | 26 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2026-03-10 | 0.667 | 26 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2026-03-10 | 0.667 | 26 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2026-03-10 | 0.667 | 26 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2026-03-10 | 0.667 | 26 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OXY-2026-03-10 | 0.667 | 26 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
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
