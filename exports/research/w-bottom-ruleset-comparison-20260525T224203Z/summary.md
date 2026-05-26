# W-Bottom Ruleset Comparison Backtest Summary

**Cohort:** composite>=0.5 double_bottom_w; recency<=365d (max_observed_asof) (65 unique W patterns)

**Cohort source:** tests\fixtures\research\r2a_tightness_days_required\cohort.json

**Recency filter:** trough_2 within 365 calendar days of max_observed_asof (65 of 65 verdicts passed).

**Both-exist diagnostic:** 0 ticker-reads hit Shape A + legacy (Shape A wins per OQ-18).

**Rulesets:** 6 (A_minervini_trail_ma + B_fixed_R_multiple + C_close_below_50d + D_minervini_stage2_progression + E_oneil_cup_with_handle_measured_move + F_qullamaggie_momentum_burst).

## Cross-ruleset comparison (ranked by expectancy_R_closed)

| Rank | Ruleset | Win-rate | Mean R closed | Std R closed | Mean R triggered | Max drawdown closed | Avg sessions closed |
|------|---------|----------|---------------|--------------|------------------|---------------------|---------------------|
| 1 | F_qullamaggie_momentum_burst | 0.0% | -0.154R | 0.205R | -0.129R | +1.848R | 5.0d |
| 2 | A_minervini_trail_ma | 0.0% | -0.234R | 0.232R | -0.160R | +1.853R | 5.2d |
| 3 | C_close_below_50d | 0.0% | -0.234R | 0.232R | -0.160R | +1.853R | 5.2d |
| 4 | E_oneil_cup_with_handle_measured_move | 22.5% | -1.086R | 0.961R | -0.680R | +2.637R | 4.2d |
| 5 | B_fixed_R_multiple | 0.0% | -1.316R | n/a | -0.143R | +1.711R | 4.0d |
| 6 | D_minervini_stage2_progression | 0.0% | -1.316R | n/a | -0.143R | +1.711R | 4.0d |

## Per-ruleset aggregate stats

| Ruleset | Patterns | Triggered | Closed | Winners | Losers | Untrig | Open | Win-rate | Avg R win | Avg R loser | Expectancy R closed | Avg sessions held (closed) | Avg sessions held (open) |
|---------|----------|-----------|--------|---------|--------|--------|------|----------|-----------|-------------|---------------------|------------------------|----------------------|
| A_minervini_trail_ma | 65 | 62 | 45 | 0 | 45 | 3 | 17 | 0.0% | n/a | -0.234R | -0.234R | 5.2d | 10.6d |
| B_fixed_R_multiple | 65 | 62 | 1 | 0 | 1 | 3 | 61 | 0.0% | n/a | -1.316R | -1.316R | 4.0d | 11.9d |
| C_close_below_50d | 65 | 62 | 45 | 0 | 45 | 3 | 17 | 0.0% | n/a | -0.234R | -0.234R | 5.2d | 10.6d |
| D_minervini_stage2_progression | 65 | 62 | 1 | 0 | 1 | 3 | 61 | 0.0% | n/a | -1.316R | -1.316R | 4.0d | 11.9d |
| E_oneil_cup_with_handle_measured_move | 65 | 62 | 40 | 9 | 31 | 3 | 22 | 22.5% | +0.512R | -1.550R | -1.086R | 4.2d | 10.2d |
| F_qullamaggie_momentum_burst | 65 | 62 | 56 | 0 | 56 | 3 | 6 | 0.0% | n/a | -0.154R | -0.154R | 5.0d | 15.7d |

## Exit-reason breakdown

| Ruleset | close_below_50d | momentum_gate_fail | open_at_data_tail | stop_hit | target_measured_move | untriggered |
|---------|-----------------|--------------------|-------------------|----------|----------------------|-------------|
| A_minervini_trail_ma | 45 | 0 | 17 | 0 | 0 | 3 |
| B_fixed_R_multiple | 0 | 0 | 61 | 1 | 0 | 3 |
| C_close_below_50d | 44 | 0 | 17 | 1 | 0 | 3 |
| D_minervini_stage2_progression | 0 | 0 | 61 | 1 | 0 | 3 |
| E_oneil_cup_with_handle_measured_move | 0 | 0 | 22 | 31 | 9 | 3 |
| F_qullamaggie_momentum_burst | 0 | 55 | 6 | 1 | 0 | 3 |

## Per-composite-score-bucket analysis

| Bucket | Ruleset | Patterns | Triggered | Closed | Winners | Expectancy R closed |
|--------|---------|----------|-----------|--------|---------|---------------------|
| composite_0.7_to_0.9 | A_minervini_trail_ma | 15 | 15 | 12 | 0 | -0.213R |
| composite_0.7_to_0.9 | B_fixed_R_multiple | 15 | 15 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | C_close_below_50d | 15 | 15 | 12 | 0 | -0.213R |
| composite_0.7_to_0.9 | D_minervini_stage2_progression | 15 | 15 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | E_oneil_cup_with_handle_measured_move | 15 | 15 | 10 | 4 | -0.785R |
| composite_0.7_to_0.9 | F_qullamaggie_momentum_burst | 15 | 15 | 15 | 0 | -0.116R |
| composite_0.9_plus | A_minervini_trail_ma | 2 | 2 | 1 | 0 | -0.304R |
| composite_0.9_plus | B_fixed_R_multiple | 2 | 2 | 0 | 0 | n/a |
| composite_0.9_plus | C_close_below_50d | 2 | 2 | 1 | 0 | -0.304R |
| composite_0.9_plus | D_minervini_stage2_progression | 2 | 2 | 0 | 0 | n/a |
| composite_0.9_plus | E_oneil_cup_with_handle_measured_move | 2 | 2 | 1 | 0 | -2.027R |
| composite_0.9_plus | F_qullamaggie_momentum_burst | 2 | 2 | 2 | 0 | -0.194R |
| composite_below_0.7 | A_minervini_trail_ma | 48 | 45 | 32 | 0 | -0.240R |
| composite_below_0.7 | B_fixed_R_multiple | 48 | 45 | 1 | 0 | -1.316R |
| composite_below_0.7 | C_close_below_50d | 48 | 45 | 32 | 0 | -0.240R |
| composite_below_0.7 | D_minervini_stage2_progression | 48 | 45 | 1 | 0 | -1.316R |
| composite_below_0.7 | E_oneil_cup_with_handle_measured_move | 48 | 45 | 29 | 5 | -1.157R |
| composite_below_0.7 | F_qullamaggie_momentum_burst | 48 | 45 | 39 | 0 | -0.167R |

## Per-pattern detail (first 390 rows; sorted by ticker then trough_1_date)

| pattern_id | composite | days_t2_to_asof | ruleset | status | entry_date | exit_date | exit_reason | R-multiple | sessions_held | peak_R | dd_to_exit_R | pnl_$ |
|------------|-----------|-----------------|---------|--------|------------|-----------|-------------|------------|---------------|--------|--------------|-------|
| FRO-2025-05-22 | 0.667 | 323 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.051R | 16 | +0.191R | +0.139R | $+1.93 |
| FRO-2025-05-22 | 0.667 | 323 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.051R | 16 | +0.191R | +0.139R | $+1.93 |
| FRO-2025-05-22 | 0.667 | 323 | C_close_below_50d | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.051R | 16 | +0.191R | +0.139R | $+1.93 |
| FRO-2025-05-22 | 0.667 | 323 | D_minervini_stage2_progression | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.051R | 16 | +0.191R | +0.139R | $+1.93 |
| FRO-2025-05-22 | 0.667 | 323 | E_oneil_cup_with_handle_measured_move | closed | 2026-04-30 | 2026-05-05 | target_measured_move | +0.543R | 3 | +0.813R | +0.270R | $+20.36 |
| FRO-2025-05-22 | 0.667 | 323 | F_qullamaggie_momentum_burst | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.051R | 16 | +0.191R | +0.139R | $+1.93 |
| FRO-2025-06-09 | 0.600 | 302 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.049R | 16 | +0.180R | +0.132R | $+1.83 |
| FRO-2025-06-09 | 0.600 | 302 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.049R | 16 | +0.180R | +0.132R | $+1.83 |
| FRO-2025-06-09 | 0.600 | 302 | C_close_below_50d | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.049R | 16 | +0.180R | +0.132R | $+1.83 |
| FRO-2025-06-09 | 0.600 | 302 | D_minervini_stage2_progression | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.049R | 16 | +0.180R | +0.132R | $+1.83 |
| FRO-2025-06-09 | 0.600 | 302 | E_oneil_cup_with_handle_measured_move | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.335R | 16 | +1.241R | +0.906R | $+12.58 |
| FRO-2025-06-09 | 0.600 | 302 | F_qullamaggie_momentum_burst | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.049R | 16 | +0.180R | +0.132R | $+1.83 |
| FRO-2025-06-30 | 0.667 | 281 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.053R | 16 | +0.197R | +0.144R | $+1.99 |
| FRO-2025-06-30 | 0.667 | 281 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.053R | 16 | +0.197R | +0.144R | $+1.99 |
| FRO-2025-06-30 | 0.667 | 281 | C_close_below_50d | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.053R | 16 | +0.197R | +0.144R | $+1.99 |
| FRO-2025-06-30 | 0.667 | 281 | D_minervini_stage2_progression | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.053R | 16 | +0.197R | +0.144R | $+1.99 |
| FRO-2025-06-30 | 0.667 | 281 | E_oneil_cup_with_handle_measured_move | closed | 2026-04-30 | 2026-05-08 | target_measured_move | +0.923R | 6 | +1.176R | +0.252R | $+34.62 |
| FRO-2025-06-30 | 0.667 | 281 | F_qullamaggie_momentum_burst | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.053R | 16 | +0.197R | +0.144R | $+1.99 |
| FRO-2025-07-21 | 0.667 | 260 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.054R | 16 | +0.201R | +0.147R | $+2.04 |
| FRO-2025-07-21 | 0.667 | 260 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.054R | 16 | +0.201R | +0.147R | $+2.04 |
| FRO-2025-07-21 | 0.667 | 260 | C_close_below_50d | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.054R | 16 | +0.201R | +0.147R | $+2.04 |
| FRO-2025-07-21 | 0.667 | 260 | D_minervini_stage2_progression | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.054R | 16 | +0.201R | +0.147R | $+2.04 |
| FRO-2025-07-21 | 0.667 | 260 | E_oneil_cup_with_handle_measured_move | closed | 2026-04-30 | 2026-05-08 | target_measured_move | +0.837R | 6 | +1.176R | +0.339R | $+31.38 |
| FRO-2025-07-21 | 0.667 | 260 | F_qullamaggie_momentum_burst | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.054R | 16 | +0.201R | +0.147R | $+2.04 |
| FRO-2026-01-02 | 0.656 | 46 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| FRO-2026-01-02 | 0.656 | 46 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| FRO-2026-01-02 | 0.656 | 46 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| FRO-2026-01-02 | 0.656 | 46 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| FRO-2026-01-02 | 0.656 | 46 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| FRO-2026-01-02 | 0.656 | 46 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| FRO-2026-03-13 | 0.667 | 29 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.314R | 16 | +1.160R | +0.847R | $+11.76 |
| FRO-2026-03-13 | 0.667 | 29 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.314R | 16 | +1.160R | +0.847R | $+11.76 |
| FRO-2026-03-13 | 0.667 | 29 | C_close_below_50d | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.314R | 16 | +1.160R | +0.847R | $+11.76 |
| FRO-2026-03-13 | 0.667 | 29 | D_minervini_stage2_progression | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.314R | 16 | +1.160R | +0.847R | $+11.76 |
| FRO-2026-03-13 | 0.667 | 29 | E_oneil_cup_with_handle_measured_move | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.335R | 16 | +1.241R | +0.906R | $+12.58 |
| FRO-2026-03-13 | 0.667 | 29 | F_qullamaggie_momentum_burst | open | 2026-04-30 | 2026-05-22 | open_at_data_tail | +0.314R | 16 | +1.160R | +0.847R | $+11.76 |
| FRO-2026-03-30 | 0.667 | 14 | A_minervini_trail_ma | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | +0.107R | 14 | +0.986R | +0.879R | $+4.02 |
| FRO-2026-03-30 | 0.667 | 14 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | +0.107R | 14 | +0.986R | +0.879R | $+4.02 |
| FRO-2026-03-30 | 0.667 | 14 | C_close_below_50d | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | +0.107R | 14 | +0.986R | +0.879R | $+4.02 |
| FRO-2026-03-30 | 0.667 | 14 | D_minervini_stage2_progression | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | +0.107R | 14 | +0.986R | +0.879R | $+4.02 |
| FRO-2026-03-30 | 0.667 | 14 | E_oneil_cup_with_handle_measured_move | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | +0.109R | 14 | +0.999R | +0.890R | $+4.08 |
| FRO-2026-03-30 | 0.667 | 14 | F_qullamaggie_momentum_burst | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | +0.107R | 14 | +0.986R | +0.879R | $+4.02 |
| KOD-2025-04-08 | 0.500 | 356 | A_minervini_trail_ma | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.211R | 10 | +0.081R | +0.292R | $-7.91 |
| KOD-2025-04-08 | 0.500 | 356 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.181R | 14 | +0.081R | +0.261R | $-6.77 |
| KOD-2025-04-08 | 0.500 | 356 | C_close_below_50d | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.211R | 10 | +0.081R | +0.292R | $-7.91 |
| KOD-2025-04-08 | 0.500 | 356 | D_minervini_stage2_progression | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.181R | 14 | +0.081R | +0.261R | $-6.77 |
| KOD-2025-04-08 | 0.500 | 356 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-04 | 2026-05-11 | stop_hit | -1.020R | 5 | +0.922R | +1.942R | $-38.24 |
| KOD-2025-04-08 | 0.500 | 356 | F_qullamaggie_momentum_burst | closed | 2026-05-04 | 2026-05-11 | momentum_gate_fail | -0.016R | 5 | +0.081R | +0.097R | $-0.60 |
| KOD-2025-05-15 | 0.833 | 335 | A_minervini_trail_ma | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.209R | 10 | +0.080R | +0.289R | $-7.84 |
| KOD-2025-05-15 | 0.833 | 335 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.179R | 14 | +0.080R | +0.259R | $-6.71 |
| KOD-2025-05-15 | 0.833 | 335 | C_close_below_50d | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.209R | 10 | +0.080R | +0.289R | $-7.84 |
| KOD-2025-05-15 | 0.833 | 335 | D_minervini_stage2_progression | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.179R | 14 | +0.080R | +0.259R | $-6.71 |
| KOD-2025-05-15 | 0.833 | 335 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-04 | 2026-05-06 | target_measured_move | +0.210R | 2 | +0.922R | +0.712R | $+7.89 |
| KOD-2025-05-15 | 0.833 | 335 | F_qullamaggie_momentum_burst | closed | 2026-05-04 | 2026-05-11 | momentum_gate_fail | -0.016R | 5 | +0.080R | +0.096R | $-0.59 |
| KOD-2025-05-30 | 0.833 | 316 | A_minervini_trail_ma | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.210R | 10 | +0.080R | +0.290R | $-7.87 |
| KOD-2025-05-30 | 0.833 | 316 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.179R | 14 | +0.080R | +0.260R | $-6.73 |
| KOD-2025-05-30 | 0.833 | 316 | C_close_below_50d | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.210R | 10 | +0.080R | +0.290R | $-7.87 |
| KOD-2025-05-30 | 0.833 | 316 | D_minervini_stage2_progression | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.179R | 14 | +0.080R | +0.260R | $-6.73 |
| KOD-2025-05-30 | 0.833 | 316 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-04 | 2026-05-06 | target_measured_move | +0.236R | 2 | +0.922R | +0.686R | $+8.86 |
| KOD-2025-05-30 | 0.833 | 316 | F_qullamaggie_momentum_burst | closed | 2026-05-04 | 2026-05-11 | momentum_gate_fail | -0.016R | 5 | +0.080R | +0.096R | $-0.59 |
| KOD-2025-06-18 | 0.500 | 273 | A_minervini_trail_ma | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.227R | 10 | +0.087R | +0.314R | $-8.51 |
| KOD-2025-06-18 | 0.500 | 273 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.194R | 14 | +0.087R | +0.281R | $-7.28 |
| KOD-2025-06-18 | 0.500 | 273 | C_close_below_50d | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.227R | 10 | +0.087R | +0.314R | $-8.51 |
| KOD-2025-06-18 | 0.500 | 273 | D_minervini_stage2_progression | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.194R | 14 | +0.087R | +0.281R | $-7.28 |
| KOD-2025-06-18 | 0.500 | 273 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-04 | 2026-05-11 | stop_hit | -1.020R | 5 | +0.922R | +1.942R | $-38.24 |
| KOD-2025-06-18 | 0.500 | 273 | F_qullamaggie_momentum_burst | closed | 2026-05-04 | 2026-05-11 | momentum_gate_fail | -0.017R | 5 | +0.087R | +0.104R | $-0.64 |
| KOD-2025-07-31 | 0.667 | 238 | A_minervini_trail_ma | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.240R | 10 | +0.092R | +0.331R | $-8.99 |
| KOD-2025-07-31 | 0.667 | 238 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.205R | 14 | +0.092R | +0.297R | $-7.69 |
| KOD-2025-07-31 | 0.667 | 238 | C_close_below_50d | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.240R | 10 | +0.092R | +0.331R | $-8.99 |
| KOD-2025-07-31 | 0.667 | 238 | D_minervini_stage2_progression | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.205R | 14 | +0.092R | +0.297R | $-7.69 |
| KOD-2025-07-31 | 0.667 | 238 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-04 | 2026-05-11 | stop_hit | -1.020R | 5 | +0.922R | +1.942R | $-38.24 |
| KOD-2025-07-31 | 0.667 | 238 | F_qullamaggie_momentum_burst | closed | 2026-05-04 | 2026-05-11 | momentum_gate_fail | -0.018R | 5 | +0.092R | +0.110R | $-0.68 |
| KOD-2025-09-04 | 0.500 | 225 | A_minervini_trail_ma | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.244R | 10 | +0.093R | +0.338R | $-9.16 |
| KOD-2025-09-04 | 0.500 | 225 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.209R | 14 | +0.093R | +0.302R | $-7.83 |
| KOD-2025-09-04 | 0.500 | 225 | C_close_below_50d | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.244R | 10 | +0.093R | +0.338R | $-9.16 |
| KOD-2025-09-04 | 0.500 | 225 | D_minervini_stage2_progression | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.209R | 14 | +0.093R | +0.302R | $-7.83 |
| KOD-2025-09-04 | 0.500 | 225 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-04 | 2026-05-06 | target_measured_move | +0.568R | 2 | +0.922R | +0.354R | $+21.28 |
| KOD-2025-09-04 | 0.500 | 225 | F_qullamaggie_momentum_burst | closed | 2026-05-04 | 2026-05-11 | momentum_gate_fail | -0.018R | 5 | +0.093R | +0.112R | $-0.69 |
| KOD-2025-10-02 | 0.600 | 199 | A_minervini_trail_ma | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.262R | 10 | +0.100R | +0.363R | $-9.84 |
| KOD-2025-10-02 | 0.600 | 199 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.224R | 14 | +0.100R | +0.325R | $-8.42 |
| KOD-2025-10-02 | 0.600 | 199 | C_close_below_50d | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.262R | 10 | +0.100R | +0.363R | $-9.84 |
| KOD-2025-10-02 | 0.600 | 199 | D_minervini_stage2_progression | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.224R | 14 | +0.100R | +0.325R | $-8.42 |
| KOD-2025-10-02 | 0.600 | 199 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-04 | 2026-05-11 | stop_hit | -1.020R | 5 | +0.922R | +1.942R | $-38.24 |
| KOD-2025-10-02 | 0.600 | 199 | F_qullamaggie_momentum_burst | closed | 2026-05-04 | 2026-05-11 | momentum_gate_fail | -0.020R | 5 | +0.100R | +0.120R | $-0.74 |
| KOD-2025-10-13 | 0.500 | 189 | A_minervini_trail_ma | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.316R | 10 | +0.121R | +0.437R | $-11.87 |
| KOD-2025-10-13 | 0.500 | 189 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.271R | 14 | +0.121R | +0.392R | $-10.15 |
| KOD-2025-10-13 | 0.500 | 189 | C_close_below_50d | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.316R | 10 | +0.121R | +0.437R | $-11.87 |
| KOD-2025-10-13 | 0.500 | 189 | D_minervini_stage2_progression | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.271R | 14 | +0.121R | +0.392R | $-10.15 |
| KOD-2025-10-13 | 0.500 | 189 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-04 | 2026-05-11 | stop_hit | -1.020R | 5 | +0.922R | +1.942R | $-38.24 |
| KOD-2025-10-13 | 0.500 | 189 | F_qullamaggie_momentum_burst | closed | 2026-05-04 | 2026-05-11 | momentum_gate_fail | -0.024R | 5 | +0.121R | +0.145R | $-0.89 |
| KOD-2025-10-23 | 0.767 | 175 | A_minervini_trail_ma | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.314R | 10 | +0.120R | +0.434R | $-11.77 |
| KOD-2025-10-23 | 0.767 | 175 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.269R | 14 | +0.120R | +0.389R | $-10.07 |
| KOD-2025-10-23 | 0.767 | 175 | C_close_below_50d | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.314R | 10 | +0.120R | +0.434R | $-11.77 |
| KOD-2025-10-23 | 0.767 | 175 | D_minervini_stage2_progression | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.269R | 14 | +0.120R | +0.389R | $-10.07 |
| KOD-2025-10-23 | 0.767 | 175 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-04 | 2026-05-11 | stop_hit | -1.020R | 5 | +0.922R | +1.942R | $-38.24 |
| KOD-2025-10-23 | 0.767 | 175 | F_qullamaggie_momentum_burst | closed | 2026-05-04 | 2026-05-11 | momentum_gate_fail | -0.024R | 5 | +0.120R | +0.144R | $-0.89 |
| KOD-2025-11-06 | 0.667 | 136 | A_minervini_trail_ma | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.406R | 10 | +0.155R | +0.562R | $-15.24 |
| KOD-2025-11-06 | 0.667 | 136 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.348R | 14 | +0.155R | +0.503R | $-13.03 |
| KOD-2025-11-06 | 0.667 | 136 | C_close_below_50d | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.406R | 10 | +0.155R | +0.562R | $-15.24 |
| KOD-2025-11-06 | 0.667 | 136 | D_minervini_stage2_progression | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.348R | 14 | +0.155R | +0.503R | $-13.03 |
| KOD-2025-11-06 | 0.667 | 136 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-04 | 2026-05-11 | stop_hit | -1.020R | 5 | +0.922R | +1.942R | $-38.24 |
| KOD-2025-11-06 | 0.667 | 136 | F_qullamaggie_momentum_burst | closed | 2026-05-04 | 2026-05-11 | momentum_gate_fail | -0.031R | 5 | +0.155R | +0.186R | $-1.15 |
| KOD-2025-12-15 | 0.500 | 115 | A_minervini_trail_ma | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.449R | 10 | +0.172R | +0.621R | $-16.84 |
| KOD-2025-12-15 | 0.500 | 115 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.384R | 14 | +0.172R | +0.556R | $-14.40 |
| KOD-2025-12-15 | 0.500 | 115 | C_close_below_50d | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.449R | 10 | +0.172R | +0.621R | $-16.84 |
| KOD-2025-12-15 | 0.500 | 115 | D_minervini_stage2_progression | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.384R | 14 | +0.172R | +0.556R | $-14.40 |
| KOD-2025-12-15 | 0.500 | 115 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-04 | 2026-05-11 | stop_hit | -1.020R | 5 | +0.922R | +1.942R | $-38.24 |
| KOD-2025-12-15 | 0.500 | 115 | F_qullamaggie_momentum_burst | closed | 2026-05-04 | 2026-05-11 | momentum_gate_fail | -0.034R | 5 | +0.172R | +0.205R | $-1.27 |
| KOD-2026-01-05 | 0.839 | 84 | A_minervini_trail_ma | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.371R | 10 | +0.142R | +0.512R | $-13.89 |
| KOD-2026-01-05 | 0.839 | 84 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.317R | 14 | +0.142R | +0.459R | $-11.89 |
| KOD-2026-01-05 | 0.839 | 84 | C_close_below_50d | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.371R | 10 | +0.142R | +0.512R | $-13.89 |
| KOD-2026-01-05 | 0.839 | 84 | D_minervini_stage2_progression | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.317R | 14 | +0.142R | +0.459R | $-11.89 |
| KOD-2026-01-05 | 0.839 | 84 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-04 | 2026-05-11 | stop_hit | -1.020R | 5 | +0.922R | +1.942R | $-38.24 |
| KOD-2026-01-05 | 0.839 | 84 | F_qullamaggie_momentum_burst | closed | 2026-05-04 | 2026-05-11 | momentum_gate_fail | -0.028R | 5 | +0.142R | +0.170R | $-1.05 |
| KOD-2026-02-05 | 0.857 | 37 | A_minervini_trail_ma | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.385R | 10 | +0.147R | +0.532R | $-14.43 |
| KOD-2026-02-05 | 0.857 | 37 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.329R | 14 | +0.147R | +0.476R | $-12.34 |
| KOD-2026-02-05 | 0.857 | 37 | C_close_below_50d | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.385R | 10 | +0.147R | +0.532R | $-14.43 |
| KOD-2026-02-05 | 0.857 | 37 | D_minervini_stage2_progression | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.329R | 14 | +0.147R | +0.476R | $-12.34 |
| KOD-2026-02-05 | 0.857 | 37 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-04 | 2026-05-11 | stop_hit | -1.020R | 5 | +0.922R | +1.942R | $-38.24 |
| KOD-2026-02-05 | 0.857 | 37 | F_qullamaggie_momentum_burst | closed | 2026-05-04 | 2026-05-11 | momentum_gate_fail | -0.029R | 5 | +0.147R | +0.176R | $-1.09 |
| KOD-2026-03-24 | 0.500 | 31 | A_minervini_trail_ma | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.831R | 10 | +0.318R | +1.149R | $-31.18 |
| KOD-2026-03-24 | 0.500 | 31 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.711R | 14 | +0.318R | +1.029R | $-26.67 |
| KOD-2026-03-24 | 0.500 | 31 | C_close_below_50d | closed | 2026-05-04 | 2026-05-18 | close_below_50d | -0.831R | 10 | +0.318R | +1.149R | $-31.18 |
| KOD-2026-03-24 | 0.500 | 31 | D_minervini_stage2_progression | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.711R | 14 | +0.318R | +1.029R | $-26.67 |
| KOD-2026-03-24 | 0.500 | 31 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-04 | 2026-05-11 | stop_hit | -1.020R | 5 | +0.922R | +1.942R | $-38.24 |
| KOD-2026-03-24 | 0.500 | 31 | F_qullamaggie_momentum_burst | closed | 2026-05-04 | 2026-05-11 | momentum_gate_fail | -0.063R | 5 | +0.318R | +0.380R | $-2.35 |
| NAT-2025-04-15 | 0.500 | 348 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.036R | 0 | +0.003R | +0.039R | $-1.34 |
| NAT-2025-04-15 | 0.500 | 348 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.071R | 6 | +0.016R | +0.088R | $-2.67 |
| NAT-2025-04-15 | 0.500 | 348 | C_close_below_50d | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.036R | 0 | +0.003R | +0.039R | $-1.34 |
| NAT-2025-04-15 | 0.500 | 348 | D_minervini_stage2_progression | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.071R | 6 | +0.016R | +0.088R | $-2.67 |
| NAT-2025-04-15 | 0.500 | 348 | E_oneil_cup_with_handle_measured_move | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.489R | 6 | +0.111R | +0.601R | $-18.35 |
| NAT-2025-04-15 | 0.500 | 348 | F_qullamaggie_momentum_burst | closed | 2026-05-14 | 2026-05-21 | momentum_gate_fail | -0.006R | 5 | +0.016R | +0.023R | $-0.24 |
| NAT-2025-05-29 | 0.667 | 315 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.036R | 0 | +0.003R | +0.040R | $-1.36 |
| NAT-2025-05-29 | 0.667 | 315 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.072R | 6 | +0.016R | +0.089R | $-2.72 |
| NAT-2025-05-29 | 0.667 | 315 | C_close_below_50d | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.036R | 0 | +0.003R | +0.040R | $-1.36 |
| NAT-2025-05-29 | 0.667 | 315 | D_minervini_stage2_progression | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.072R | 6 | +0.016R | +0.089R | $-2.72 |
| NAT-2025-05-29 | 0.667 | 315 | E_oneil_cup_with_handle_measured_move | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.489R | 6 | +0.111R | +0.601R | $-18.35 |
| NAT-2025-05-29 | 0.667 | 315 | F_qullamaggie_momentum_burst | closed | 2026-05-14 | 2026-05-21 | momentum_gate_fail | -0.007R | 5 | +0.016R | +0.023R | $-0.25 |
| NAT-2025-09-29 | 0.500 | 210 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.045R | 0 | +0.004R | +0.049R | $-1.67 |
| NAT-2025-09-29 | 0.500 | 210 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.089R | 6 | +0.020R | +0.109R | $-3.34 |
| NAT-2025-09-29 | 0.500 | 210 | C_close_below_50d | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.045R | 0 | +0.004R | +0.049R | $-1.67 |
| NAT-2025-09-29 | 0.500 | 210 | D_minervini_stage2_progression | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.089R | 6 | +0.020R | +0.109R | $-3.34 |
| NAT-2025-09-29 | 0.500 | 210 | E_oneil_cup_with_handle_measured_move | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.489R | 6 | +0.111R | +0.601R | $-18.35 |
| NAT-2025-09-29 | 0.500 | 210 | F_qullamaggie_momentum_burst | closed | 2026-05-14 | 2026-05-21 | momentum_gate_fail | -0.008R | 5 | +0.020R | +0.028R | $-0.30 |
| NAT-2025-10-14 | 0.500 | 189 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.052R | 0 | +0.005R | +0.056R | $-1.93 |
| NAT-2025-10-14 | 0.500 | 189 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.103R | 6 | +0.023R | +0.126R | $-3.86 |
| NAT-2025-10-14 | 0.500 | 189 | C_close_below_50d | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.052R | 0 | +0.005R | +0.056R | $-1.93 |
| NAT-2025-10-14 | 0.500 | 189 | D_minervini_stage2_progression | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.103R | 6 | +0.023R | +0.126R | $-3.86 |
| NAT-2025-10-14 | 0.500 | 189 | E_oneil_cup_with_handle_measured_move | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.489R | 6 | +0.111R | +0.601R | $-18.35 |
| NAT-2025-10-14 | 0.500 | 189 | F_qullamaggie_momentum_burst | closed | 2026-05-14 | 2026-05-21 | momentum_gate_fail | -0.009R | 5 | +0.023R | +0.033R | $-0.35 |
| NAT-2025-11-04 | 0.767 | 144 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.048R | 0 | +0.004R | +0.053R | $-1.81 |
| NAT-2025-11-04 | 0.767 | 144 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.096R | 6 | +0.022R | +0.118R | $-3.61 |
| NAT-2025-11-04 | 0.767 | 144 | C_close_below_50d | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.048R | 0 | +0.004R | +0.053R | $-1.81 |
| NAT-2025-11-04 | 0.767 | 144 | D_minervini_stage2_progression | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.096R | 6 | +0.022R | +0.118R | $-3.61 |
| NAT-2025-11-04 | 0.767 | 144 | E_oneil_cup_with_handle_measured_move | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.489R | 6 | +0.111R | +0.601R | $-18.35 |
| NAT-2025-11-04 | 0.767 | 144 | F_qullamaggie_momentum_burst | closed | 2026-05-14 | 2026-05-21 | momentum_gate_fail | -0.009R | 5 | +0.022R | +0.031R | $-0.33 |
| NAT-2026-03-12 | 0.667 | 28 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| NAT-2026-03-12 | 0.667 | 28 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| NAT-2026-03-12 | 0.667 | 28 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| NAT-2026-03-12 | 0.667 | 28 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| NAT-2026-03-12 | 0.667 | 28 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| NAT-2026-03-12 | 0.667 | 28 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| NAT-2026-04-14 | 0.600 | 19 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| NAT-2026-04-14 | 0.600 | 19 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| NAT-2026-04-14 | 0.600 | 19 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| NAT-2026-04-14 | 0.600 | 19 | D_minervini_stage2_progression | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| NAT-2026-04-14 | 0.600 | 19 | E_oneil_cup_with_handle_measured_move | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| NAT-2026-04-14 | 0.600 | 19 | F_qullamaggie_momentum_burst | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| OII-2025-08-01 | 0.500 | 193 | A_minervini_trail_ma | closed | 2026-04-23 | 2026-04-29 | close_below_50d | -0.018R | 4 | +0.271R | +0.289R | $-0.66 |
| OII-2025-08-01 | 0.500 | 193 | B_fixed_R_multiple | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +0.177R | 21 | +0.271R | +0.095R | $+6.62 |
| OII-2025-08-01 | 0.500 | 193 | C_close_below_50d | closed | 2026-04-23 | 2026-04-29 | close_below_50d | -0.018R | 4 | +0.271R | +0.289R | $-0.66 |
| OII-2025-08-01 | 0.500 | 193 | D_minervini_stage2_progression | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +0.177R | 21 | +0.271R | +0.095R | $+6.62 |
| OII-2025-08-01 | 0.500 | 193 | E_oneil_cup_with_handle_measured_move | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +0.869R | 21 | +1.334R | +0.466R | $+32.59 |
| OII-2025-08-01 | 0.500 | 193 | F_qullamaggie_momentum_burst | closed | 2026-04-23 | 2026-04-30 | momentum_gate_fail | -0.017R | 5 | +0.271R | +0.288R | $-0.63 |
| OII-2025-10-10 | 0.667 | 166 | A_minervini_trail_ma | closed | 2026-04-23 | 2026-04-29 | close_below_50d | -0.018R | 4 | +0.279R | +0.297R | $-0.68 |
| OII-2025-10-10 | 0.667 | 166 | B_fixed_R_multiple | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +0.182R | 21 | +0.279R | +0.097R | $+6.82 |
| OII-2025-10-10 | 0.667 | 166 | C_close_below_50d | closed | 2026-04-23 | 2026-04-29 | close_below_50d | -0.018R | 4 | +0.279R | +0.297R | $-0.68 |
| OII-2025-10-10 | 0.667 | 166 | D_minervini_stage2_progression | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +0.182R | 21 | +0.279R | +0.097R | $+6.82 |
| OII-2025-10-10 | 0.667 | 166 | E_oneil_cup_with_handle_measured_move | closed | 2026-04-23 | 2026-05-13 | target_measured_move | +0.862R | 14 | +1.334R | +0.472R | $+32.33 |
| OII-2025-10-10 | 0.667 | 166 | F_qullamaggie_momentum_burst | closed | 2026-04-23 | 2026-04-30 | momentum_gate_fail | -0.017R | 5 | +0.279R | +0.296R | $-0.65 |
| OII-2025-11-06 | 0.667 | 124 | A_minervini_trail_ma | closed | 2026-04-23 | 2026-04-29 | close_below_50d | -0.019R | 4 | +0.294R | +0.313R | $-0.71 |
| OII-2025-11-06 | 0.667 | 124 | B_fixed_R_multiple | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +0.191R | 21 | +0.294R | +0.102R | $+7.17 |
| OII-2025-11-06 | 0.667 | 124 | C_close_below_50d | closed | 2026-04-23 | 2026-04-29 | close_below_50d | -0.019R | 4 | +0.294R | +0.313R | $-0.71 |
| OII-2025-11-06 | 0.667 | 124 | D_minervini_stage2_progression | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +0.191R | 21 | +0.294R | +0.102R | $+7.17 |
| OII-2025-11-06 | 0.667 | 124 | E_oneil_cup_with_handle_measured_move | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +0.869R | 21 | +1.334R | +0.466R | $+32.59 |
| OII-2025-11-06 | 0.667 | 124 | F_qullamaggie_momentum_burst | closed | 2026-04-23 | 2026-04-30 | momentum_gate_fail | -0.018R | 5 | +0.294R | +0.312R | $-0.68 |
| OII-2025-12-18 | 0.500 | 39 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.038R | 6 | +0.127R | +0.165R | $-1.42 |
| OII-2025-12-18 | 0.500 | 39 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.038R | 6 | +0.127R | +0.165R | $-1.42 |
| OII-2025-12-18 | 0.500 | 39 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.038R | 6 | +0.127R | +0.165R | $-1.42 |
| OII-2025-12-18 | 0.500 | 39 | D_minervini_stage2_progression | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.038R | 6 | +0.127R | +0.165R | $-1.42 |
| OII-2025-12-18 | 0.500 | 39 | E_oneil_cup_with_handle_measured_move | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.074R | 6 | +0.247R | +0.321R | $-2.76 |
| OII-2025-12-18 | 0.500 | 39 | F_qullamaggie_momentum_burst | closed | 2026-05-14 | 2026-05-21 | momentum_gate_fail | -0.046R | 5 | +0.127R | +0.173R | $-1.73 |
| OII-2026-03-13 | 0.833 | 20 | A_minervini_trail_ma | closed | 2026-04-23 | 2026-04-29 | close_below_50d | -0.112R | 4 | +1.740R | +1.853R | $-4.22 |
| OII-2026-03-13 | 0.833 | 20 | B_fixed_R_multiple | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.133R | 21 | +1.740R | +0.607R | $+42.50 |
| OII-2026-03-13 | 0.833 | 20 | C_close_below_50d | closed | 2026-04-23 | 2026-04-29 | close_below_50d | -0.112R | 4 | +1.740R | +1.853R | $-4.22 |
| OII-2026-03-13 | 0.833 | 20 | D_minervini_stage2_progression | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.133R | 21 | +1.740R | +0.607R | $+42.50 |
| OII-2026-03-13 | 0.833 | 20 | E_oneil_cup_with_handle_measured_move | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.133R | 21 | +1.740R | +0.607R | $+42.50 |
| OII-2026-03-13 | 0.833 | 20 | F_qullamaggie_momentum_burst | closed | 2026-04-23 | 2026-04-30 | momentum_gate_fail | -0.108R | 5 | +1.740R | +1.848R | $-4.05 |
| RLMD-2025-05-21 | 0.667 | 317 | A_minervini_trail_ma | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.056R | 3 | +0.057R | +0.113R | $-2.11 |
| RLMD-2025-05-21 | 0.667 | 317 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.036R | 8 | +0.057R | +0.093R | $-1.33 |
| RLMD-2025-05-21 | 0.667 | 317 | C_close_below_50d | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.056R | 3 | +0.057R | +0.113R | $-2.11 |
| RLMD-2025-05-21 | 0.667 | 317 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.036R | 8 | +0.057R | +0.093R | $-1.33 |
| RLMD-2025-05-21 | 0.667 | 317 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-12 | 2026-05-18 | stop_hit | -1.614R | 4 | +0.661R | +2.275R | $-60.53 |
| RLMD-2025-05-21 | 0.667 | 317 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.142R | 5 | +0.057R | +0.199R | $-5.33 |
| RLMD-2025-06-30 | 0.767 | 294 | A_minervini_trail_ma | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.057R | 3 | +0.057R | +0.114R | $-2.12 |
| RLMD-2025-06-30 | 0.767 | 294 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.036R | 8 | +0.057R | +0.093R | $-1.34 |
| RLMD-2025-06-30 | 0.767 | 294 | C_close_below_50d | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.057R | 3 | +0.057R | +0.114R | $-2.12 |
| RLMD-2025-06-30 | 0.767 | 294 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.036R | 8 | +0.057R | +0.093R | $-1.34 |
| RLMD-2025-06-30 | 0.767 | 294 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-12 | 2026-05-12 | target_measured_move | +0.160R | 0 | +0.343R | +0.184R | $+5.99 |
| RLMD-2025-06-30 | 0.767 | 294 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.143R | 5 | +0.057R | +0.200R | $-5.37 |
| RLMD-2025-07-18 | 0.767 | 270 | A_minervini_trail_ma | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.057R | 3 | +0.057R | +0.114R | $-2.12 |
| RLMD-2025-07-18 | 0.767 | 270 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.036R | 8 | +0.057R | +0.093R | $-1.34 |
| RLMD-2025-07-18 | 0.767 | 270 | C_close_below_50d | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.057R | 3 | +0.057R | +0.114R | $-2.12 |
| RLMD-2025-07-18 | 0.767 | 270 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.036R | 8 | +0.057R | +0.093R | $-1.34 |
| RLMD-2025-07-18 | 0.767 | 270 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-12 | 2026-05-12 | target_measured_move | +0.268R | 0 | +0.343R | +0.076R | $+10.04 |
| RLMD-2025-07-18 | 0.767 | 270 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.143R | 5 | +0.057R | +0.200R | $-5.36 |
| RLMD-2025-08-11 | 0.500 | 213 | A_minervini_trail_ma | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.072R | 3 | +0.073R | +0.144R | $-2.68 |
| RLMD-2025-08-11 | 0.500 | 213 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.045R | 8 | +0.073R | +0.118R | $-1.69 |
| RLMD-2025-08-11 | 0.500 | 213 | C_close_below_50d | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.072R | 3 | +0.073R | +0.144R | $-2.68 |
| RLMD-2025-08-11 | 0.500 | 213 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.045R | 8 | +0.073R | +0.118R | $-1.69 |
| RLMD-2025-08-11 | 0.500 | 213 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-12 | 2026-05-18 | stop_hit | -1.614R | 4 | +0.661R | +2.275R | $-60.53 |
| RLMD-2025-08-11 | 0.500 | 213 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.181R | 5 | +0.073R | +0.253R | $-6.78 |
| RLMD-2025-10-07 | 0.600 | 206 | A_minervini_trail_ma | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.071R | 3 | +0.072R | +0.142R | $-2.65 |
| RLMD-2025-10-07 | 0.600 | 206 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.045R | 8 | +0.072R | +0.116R | $-1.68 |
| RLMD-2025-10-07 | 0.600 | 206 | C_close_below_50d | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.071R | 3 | +0.072R | +0.142R | $-2.65 |
| RLMD-2025-10-07 | 0.600 | 206 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.045R | 8 | +0.072R | +0.116R | $-1.68 |
| RLMD-2025-10-07 | 0.600 | 206 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-12 | 2026-05-18 | stop_hit | -1.614R | 4 | +0.661R | +2.275R | $-60.53 |
| RLMD-2025-10-07 | 0.600 | 206 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.179R | 5 | +0.072R | +0.250R | $-6.70 |
| RLMD-2025-10-14 | 0.500 | 186 | A_minervini_trail_ma | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.074R | 3 | +0.075R | +0.150R | $-2.79 |
| RLMD-2025-10-14 | 0.500 | 186 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.047R | 8 | +0.075R | +0.123R | $-1.76 |
| RLMD-2025-10-14 | 0.500 | 186 | C_close_below_50d | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.074R | 3 | +0.075R | +0.150R | $-2.79 |
| RLMD-2025-10-14 | 0.500 | 186 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.047R | 8 | +0.075R | +0.123R | $-1.76 |
| RLMD-2025-10-14 | 0.500 | 186 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-12 | 2026-05-18 | stop_hit | -1.614R | 4 | +0.661R | +2.275R | $-60.53 |
| RLMD-2025-10-14 | 0.500 | 186 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.188R | 5 | +0.075R | +0.264R | $-7.06 |
| RLMD-2025-11-03 | 0.500 | 155 | A_minervini_trail_ma | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.114R | 3 | +0.116R | +0.230R | $-4.29 |
| RLMD-2025-11-03 | 0.500 | 155 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.072R | 8 | +0.116R | +0.188R | $-2.71 |
| RLMD-2025-11-03 | 0.500 | 155 | C_close_below_50d | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.114R | 3 | +0.116R | +0.230R | $-4.29 |
| RLMD-2025-11-03 | 0.500 | 155 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.072R | 8 | +0.116R | +0.188R | $-2.71 |
| RLMD-2025-11-03 | 0.500 | 155 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-12 | 2026-05-18 | stop_hit | -1.614R | 4 | +0.661R | +2.275R | $-60.53 |
| RLMD-2025-11-03 | 0.500 | 155 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.289R | 5 | +0.116R | +0.405R | $-10.84 |
| RLMD-2025-12-04 | 0.500 | 142 | A_minervini_trail_ma | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.115R | 3 | +0.116R | +0.231R | $-4.31 |
| RLMD-2025-12-04 | 0.500 | 142 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.073R | 8 | +0.116R | +0.189R | $-2.72 |
| RLMD-2025-12-04 | 0.500 | 142 | C_close_below_50d | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.115R | 3 | +0.116R | +0.231R | $-4.31 |
| RLMD-2025-12-04 | 0.500 | 142 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.073R | 8 | +0.116R | +0.189R | $-2.72 |
| RLMD-2025-12-04 | 0.500 | 142 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-12 | 2026-05-18 | stop_hit | -1.614R | 4 | +0.661R | +2.275R | $-60.53 |
| RLMD-2025-12-04 | 0.500 | 142 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.290R | 5 | +0.116R | +0.406R | $-10.88 |
| RLMD-2025-12-17 | 0.600 | 98 | A_minervini_trail_ma | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.101R | 3 | +0.102R | +0.203R | $-3.78 |
| RLMD-2025-12-17 | 0.600 | 98 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.064R | 8 | +0.102R | +0.166R | $-2.39 |
| RLMD-2025-12-17 | 0.600 | 98 | C_close_below_50d | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.101R | 3 | +0.102R | +0.203R | $-3.78 |
| RLMD-2025-12-17 | 0.600 | 98 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.064R | 8 | +0.102R | +0.166R | $-2.39 |
| RLMD-2025-12-17 | 0.600 | 98 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-12 | 2026-05-18 | stop_hit | -1.614R | 4 | +0.661R | +2.275R | $-60.53 |
| RLMD-2025-12-17 | 0.600 | 98 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.255R | 5 | +0.102R | +0.357R | $-9.56 |
| RLMD-2026-01-30 | 0.847 | 80 | A_minervini_trail_ma | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.103R | 3 | +0.105R | +0.208R | $-3.88 |
| RLMD-2026-01-30 | 0.847 | 80 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.065R | 8 | +0.105R | +0.170R | $-2.45 |
| RLMD-2026-01-30 | 0.847 | 80 | C_close_below_50d | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.103R | 3 | +0.105R | +0.208R | $-3.88 |
| RLMD-2026-01-30 | 0.847 | 80 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.065R | 8 | +0.105R | +0.170R | $-2.45 |
| RLMD-2026-01-30 | 0.847 | 80 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-12 | 2026-05-18 | stop_hit | -1.614R | 4 | +0.661R | +2.275R | $-60.53 |
| RLMD-2026-01-30 | 0.847 | 80 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.261R | 5 | +0.105R | +0.366R | $-9.79 |
| RLMD-2026-02-17 | 0.665 | 46 | A_minervini_trail_ma | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.257R | 3 | +0.260R | +0.517R | $-9.64 |
| RLMD-2026-02-17 | 0.665 | 46 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.162R | 8 | +0.260R | +0.423R | $-6.09 |
| RLMD-2026-02-17 | 0.665 | 46 | C_close_below_50d | closed | 2026-05-12 | 2026-05-15 | close_below_50d | -0.257R | 3 | +0.260R | +0.517R | $-9.64 |
| RLMD-2026-02-17 | 0.665 | 46 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | -0.162R | 8 | +0.260R | +0.423R | $-6.09 |
| RLMD-2026-02-17 | 0.665 | 46 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-12 | 2026-05-18 | stop_hit | -1.614R | 4 | +0.661R | +2.275R | $-60.53 |
| RLMD-2026-02-17 | 0.665 | 46 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.649R | 5 | +0.260R | +0.910R | $-24.35 |
| SEI-2025-06-10 | 0.667 | 290 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.108R | +0.106R | $+0.06 |
| SEI-2025-06-10 | 0.667 | 290 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.108R | +0.106R | $+0.06 |
| SEI-2025-06-10 | 0.667 | 290 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.108R | +0.106R | $+0.06 |
| SEI-2025-06-10 | 0.667 | 290 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.108R | +0.106R | $+0.06 |
| SEI-2025-06-10 | 0.667 | 290 | E_oneil_cup_with_handle_measured_move | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.012R | 8 | +0.837R | +0.825R | $+0.44 |
| SEI-2025-06-10 | 0.667 | 290 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.085R | 5 | +0.108R | +0.192R | $-3.17 |
| SEI-2025-07-22 | 0.600 | 262 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.001R | 8 | +0.104R | +0.103R | $+0.06 |
| SEI-2025-07-22 | 0.600 | 262 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.001R | 8 | +0.104R | +0.103R | $+0.06 |
| SEI-2025-07-22 | 0.600 | 262 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.001R | 8 | +0.104R | +0.103R | $+0.06 |
| SEI-2025-07-22 | 0.600 | 262 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.001R | 8 | +0.104R | +0.103R | $+0.06 |
| SEI-2025-07-22 | 0.600 | 262 | E_oneil_cup_with_handle_measured_move | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.012R | 8 | +0.837R | +0.825R | $+0.44 |
| SEI-2025-07-22 | 0.600 | 262 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.082R | 5 | +0.104R | +0.186R | $-3.08 |
| SEI-2025-08-19 | 0.767 | 241 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.001R | 8 | +0.100R | +0.099R | $+0.05 |
| SEI-2025-08-19 | 0.767 | 241 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.001R | 8 | +0.100R | +0.099R | $+0.05 |
| SEI-2025-08-19 | 0.767 | 241 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.001R | 8 | +0.100R | +0.099R | $+0.05 |
| SEI-2025-08-19 | 0.767 | 241 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.001R | 8 | +0.100R | +0.099R | $+0.05 |
| SEI-2025-08-19 | 0.767 | 241 | E_oneil_cup_with_handle_measured_move | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.012R | 8 | +0.837R | +0.825R | $+0.44 |
| SEI-2025-08-19 | 0.767 | 241 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.079R | 5 | +0.100R | +0.179R | $-2.96 |
| SEI-2025-09-09 | 0.500 | 198 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.176R | +0.173R | $+0.09 |
| SEI-2025-09-09 | 0.500 | 198 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.176R | +0.173R | $+0.09 |
| SEI-2025-09-09 | 0.500 | 198 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.176R | +0.173R | $+0.09 |
| SEI-2025-09-09 | 0.500 | 198 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.176R | +0.173R | $+0.09 |
| SEI-2025-09-09 | 0.500 | 198 | E_oneil_cup_with_handle_measured_move | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.012R | 8 | +0.837R | +0.825R | $+0.44 |
| SEI-2025-09-09 | 0.500 | 198 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.138R | 5 | +0.176R | +0.314R | $-5.19 |
| SEI-2025-10-22 | 0.767 | 169 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.149R | +0.147R | $+0.08 |
| SEI-2025-10-22 | 0.767 | 169 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.149R | +0.147R | $+0.08 |
| SEI-2025-10-22 | 0.767 | 169 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.149R | +0.147R | $+0.08 |
| SEI-2025-10-22 | 0.767 | 169 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.149R | +0.147R | $+0.08 |
| SEI-2025-10-22 | 0.767 | 169 | E_oneil_cup_with_handle_measured_move | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.012R | 8 | +0.837R | +0.825R | $+0.44 |
| SEI-2025-10-22 | 0.767 | 169 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.117R | 5 | +0.149R | +0.266R | $-4.39 |
| SEI-2025-11-20 | 0.933 | 142 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.146R | +0.144R | $+0.08 |
| SEI-2025-11-20 | 0.933 | 142 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.146R | +0.144R | $+0.08 |
| SEI-2025-11-20 | 0.933 | 142 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.146R | +0.144R | $+0.08 |
| SEI-2025-11-20 | 0.933 | 142 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.146R | +0.144R | $+0.08 |
| SEI-2025-11-20 | 0.933 | 142 | E_oneil_cup_with_handle_measured_move | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.012R | 8 | +0.837R | +0.825R | $+0.44 |
| SEI-2025-11-20 | 0.933 | 142 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.115R | 5 | +0.146R | +0.261R | $-4.32 |
| SEI-2025-12-17 | 0.667 | 92 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.174R | +0.172R | $+0.09 |
| SEI-2025-12-17 | 0.667 | 92 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.174R | +0.172R | $+0.09 |
| SEI-2025-12-17 | 0.667 | 92 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.174R | +0.172R | $+0.09 |
| SEI-2025-12-17 | 0.667 | 92 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.002R | 8 | +0.174R | +0.172R | $+0.09 |
| SEI-2025-12-17 | 0.667 | 92 | E_oneil_cup_with_handle_measured_move | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.012R | 8 | +0.837R | +0.825R | $+0.44 |
| SEI-2025-12-17 | 0.667 | 92 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.137R | 5 | +0.174R | +0.311R | $-5.14 |
| SEI-2026-02-05 | 0.667 | 77 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.003R | 8 | +0.195R | +0.193R | $+0.10 |
| SEI-2026-02-05 | 0.667 | 77 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.003R | 8 | +0.195R | +0.193R | $+0.10 |
| SEI-2026-02-05 | 0.667 | 77 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.003R | 8 | +0.195R | +0.193R | $+0.10 |
| SEI-2026-02-05 | 0.667 | 77 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.003R | 8 | +0.195R | +0.193R | $+0.10 |
| SEI-2026-02-05 | 0.667 | 77 | E_oneil_cup_with_handle_measured_move | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.012R | 8 | +0.837R | +0.825R | $+0.44 |
| SEI-2026-02-05 | 0.667 | 77 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.154R | 5 | +0.195R | +0.349R | $-5.76 |
| SEI-2026-02-20 | 0.823 | 66 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.003R | 8 | +0.184R | +0.181R | $+0.10 |
| SEI-2026-02-20 | 0.823 | 66 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.003R | 8 | +0.184R | +0.181R | $+0.10 |
| SEI-2026-02-20 | 0.823 | 66 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.003R | 8 | +0.184R | +0.181R | $+0.10 |
| SEI-2026-02-20 | 0.823 | 66 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.003R | 8 | +0.184R | +0.181R | $+0.10 |
| SEI-2026-02-20 | 0.823 | 66 | E_oneil_cup_with_handle_measured_move | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.012R | 8 | +0.837R | +0.825R | $+0.44 |
| SEI-2026-02-20 | 0.823 | 66 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.144R | 5 | +0.184R | +0.328R | $-5.42 |
| SEI-2026-03-03 | 0.659 | 39 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.003R | 8 | +0.227R | +0.224R | $+0.12 |
| SEI-2026-03-03 | 0.659 | 39 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.003R | 8 | +0.227R | +0.224R | $+0.12 |
| SEI-2026-03-03 | 0.659 | 39 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.003R | 8 | +0.227R | +0.224R | $+0.12 |
| SEI-2026-03-03 | 0.659 | 39 | D_minervini_stage2_progression | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.003R | 8 | +0.227R | +0.224R | $+0.12 |
| SEI-2026-03-03 | 0.659 | 39 | E_oneil_cup_with_handle_measured_move | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.012R | 8 | +0.837R | +0.825R | $+0.44 |
| SEI-2026-03-03 | 0.659 | 39 | F_qullamaggie_momentum_burst | closed | 2026-05-12 | 2026-05-19 | momentum_gate_fail | -0.179R | 5 | +0.227R | +0.406R | $-6.70 |
| TROX-2025-04-08 | 0.500 | 357 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.314R | 4 | +0.094R | +0.409R | $-11.78 |
| TROX-2025-04-08 | 0.500 | 357 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.482R | 15 | +0.094R | +0.576R | $-18.07 |
| TROX-2025-04-08 | 0.500 | 357 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.314R | 4 | +0.094R | +0.409R | $-11.78 |
| TROX-2025-04-08 | 0.500 | 357 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.482R | 15 | +0.094R | +0.576R | $-18.07 |
| TROX-2025-04-08 | 0.500 | 357 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-07 | stop_hit | -2.027R | 4 | +0.609R | +2.637R | $-76.03 |
| TROX-2025-04-08 | 0.500 | 357 | F_qullamaggie_momentum_burst | closed | 2026-05-01 | 2026-05-08 | momentum_gate_fail | -0.281R | 5 | +0.094R | +0.376R | $-10.55 |
| TROX-2025-05-07 | 0.933 | 341 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.304R | 4 | +0.091R | +0.396R | $-11.41 |
| TROX-2025-05-07 | 0.933 | 341 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.467R | 15 | +0.091R | +0.558R | $-17.50 |
| TROX-2025-05-07 | 0.933 | 341 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.304R | 4 | +0.091R | +0.396R | $-11.41 |
| TROX-2025-05-07 | 0.933 | 341 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.467R | 15 | +0.091R | +0.558R | $-17.50 |
| TROX-2025-05-07 | 0.933 | 341 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-07 | stop_hit | -2.027R | 4 | +0.609R | +2.637R | $-76.03 |
| TROX-2025-05-07 | 0.933 | 341 | F_qullamaggie_momentum_burst | closed | 2026-05-01 | 2026-05-08 | momentum_gate_fail | -0.273R | 5 | +0.091R | +0.364R | $-10.22 |
| TROX-2025-05-23 | 0.667 | 303 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.324R | 4 | +0.097R | +0.421R | $-12.15 |
| TROX-2025-05-23 | 0.667 | 303 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.497R | 15 | +0.097R | +0.594R | $-18.64 |
| TROX-2025-05-23 | 0.667 | 303 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.324R | 4 | +0.097R | +0.421R | $-12.15 |
| TROX-2025-05-23 | 0.667 | 303 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.497R | 15 | +0.097R | +0.594R | $-18.64 |
| TROX-2025-05-23 | 0.667 | 303 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-07 | stop_hit | -2.027R | 4 | +0.609R | +2.637R | $-76.03 |
| TROX-2025-05-23 | 0.667 | 303 | F_qullamaggie_momentum_burst | closed | 2026-05-01 | 2026-05-08 | momentum_gate_fail | -0.290R | 5 | +0.097R | +0.388R | $-10.88 |
| TROX-2025-06-30 | 0.767 | 264 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.235R | 4 | +0.071R | +0.305R | $-8.81 |
| TROX-2025-06-30 | 0.767 | 264 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.360R | 15 | +0.071R | +0.431R | $-13.51 |
| TROX-2025-06-30 | 0.767 | 264 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.235R | 4 | +0.071R | +0.305R | $-8.81 |
| TROX-2025-06-30 | 0.767 | 264 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.360R | 15 | +0.071R | +0.431R | $-13.51 |
| TROX-2025-06-30 | 0.767 | 264 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-07 | stop_hit | -2.027R | 4 | +0.609R | +2.637R | $-76.03 |
| TROX-2025-06-30 | 0.767 | 264 | F_qullamaggie_momentum_burst | closed | 2026-05-01 | 2026-05-08 | momentum_gate_fail | -0.210R | 5 | +0.071R | +0.281R | $-7.89 |
| TROX-2025-08-21 | 0.600 | 201 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.241R | 4 | +0.072R | +0.313R | $-9.02 |
| TROX-2025-08-21 | 0.600 | 201 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.369R | 15 | +0.072R | +0.441R | $-13.84 |
| TROX-2025-08-21 | 0.600 | 201 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.241R | 4 | +0.072R | +0.313R | $-9.02 |
| TROX-2025-08-21 | 0.600 | 201 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.369R | 15 | +0.072R | +0.441R | $-13.84 |
| TROX-2025-08-21 | 0.600 | 201 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-07 | stop_hit | -2.027R | 4 | +0.609R | +2.637R | $-76.03 |
| TROX-2025-08-21 | 0.600 | 201 | F_qullamaggie_momentum_burst | closed | 2026-05-01 | 2026-05-08 | momentum_gate_fail | -0.216R | 5 | +0.072R | +0.288R | $-8.08 |
| TROX-2025-10-17 | 0.600 | 174 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.236R | 4 | +0.071R | +0.307R | $-8.84 |
| TROX-2025-10-17 | 0.600 | 174 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.362R | 15 | +0.071R | +0.433R | $-13.56 |
| TROX-2025-10-17 | 0.600 | 174 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.236R | 4 | +0.071R | +0.307R | $-8.84 |
| TROX-2025-10-17 | 0.600 | 174 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.362R | 15 | +0.071R | +0.433R | $-13.56 |
| TROX-2025-10-17 | 0.600 | 174 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-07 | stop_hit | -2.027R | 4 | +0.609R | +2.637R | $-76.03 |
| TROX-2025-10-17 | 0.600 | 174 | F_qullamaggie_momentum_burst | closed | 2026-05-01 | 2026-05-08 | momentum_gate_fail | -0.211R | 5 | +0.071R | +0.282R | $-7.92 |
| TROX-2025-11-06 | 0.600 | 160 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.226R | 4 | +0.068R | +0.294R | $-8.49 |
| TROX-2025-11-06 | 0.600 | 160 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.347R | 15 | +0.068R | +0.415R | $-13.02 |
| TROX-2025-11-06 | 0.600 | 160 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.226R | 4 | +0.068R | +0.294R | $-8.49 |
| TROX-2025-11-06 | 0.600 | 160 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.347R | 15 | +0.068R | +0.415R | $-13.02 |
| TROX-2025-11-06 | 0.600 | 160 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-07 | stop_hit | -2.027R | 4 | +0.609R | +2.637R | $-76.03 |
| TROX-2025-11-06 | 0.600 | 160 | F_qullamaggie_momentum_burst | closed | 2026-05-01 | 2026-05-08 | momentum_gate_fail | -0.203R | 5 | +0.068R | +0.271R | $-7.61 |
| TROX-2025-11-20 | 0.667 | 142 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.257R | 4 | +0.077R | +0.335R | $-9.64 |
| TROX-2025-11-20 | 0.667 | 142 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.394R | 15 | +0.077R | +0.472R | $-14.79 |
| TROX-2025-11-20 | 0.667 | 142 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.257R | 4 | +0.077R | +0.335R | $-9.64 |
| TROX-2025-11-20 | 0.667 | 142 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.394R | 15 | +0.077R | +0.472R | $-14.79 |
| TROX-2025-11-20 | 0.667 | 142 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-07 | stop_hit | -2.027R | 4 | +0.609R | +2.637R | $-76.03 |
| TROX-2025-11-20 | 0.667 | 142 | F_qullamaggie_momentum_burst | closed | 2026-05-01 | 2026-05-08 | momentum_gate_fail | -0.230R | 5 | +0.077R | +0.308R | $-8.64 |
| TROX-2026-01-30 | 0.500 | 68 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.499R | 4 | +0.150R | +0.649R | $-18.70 |
| TROX-2026-01-30 | 0.500 | 68 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.765R | 15 | +0.150R | +0.915R | $-28.68 |
| TROX-2026-01-30 | 0.500 | 68 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.499R | 4 | +0.150R | +0.649R | $-18.70 |
| TROX-2026-01-30 | 0.500 | 68 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.765R | 15 | +0.150R | +0.915R | $-28.68 |
| TROX-2026-01-30 | 0.500 | 68 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-07 | stop_hit | -2.027R | 4 | +0.609R | +2.637R | $-76.03 |
| TROX-2026-01-30 | 0.500 | 68 | F_qullamaggie_momentum_burst | closed | 2026-05-01 | 2026-05-08 | momentum_gate_fail | -0.447R | 5 | +0.150R | +0.597R | $-16.75 |
| TROX-2026-02-20 | 0.834 | 54 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.456R | 4 | +0.137R | +0.593R | $-17.10 |
| TROX-2026-02-20 | 0.834 | 54 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.699R | 15 | +0.137R | +0.836R | $-26.22 |
| TROX-2026-02-20 | 0.834 | 54 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.456R | 4 | +0.137R | +0.593R | $-17.10 |
| TROX-2026-02-20 | 0.834 | 54 | D_minervini_stage2_progression | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.699R | 15 | +0.137R | +0.836R | $-26.22 |
| TROX-2026-02-20 | 0.834 | 54 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-07 | stop_hit | -2.027R | 4 | +0.609R | +2.637R | $-76.03 |
| TROX-2026-02-20 | 0.834 | 54 | F_qullamaggie_momentum_burst | closed | 2026-05-01 | 2026-05-08 | momentum_gate_fail | -0.408R | 5 | +0.137R | +0.545R | $-15.31 |
| TROX-2026-03-20 | 0.667 | 20 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -1.316R | 4 | +0.395R | +1.711R | $-49.33 |
| TROX-2026-03-20 | 0.667 | 20 | B_fixed_R_multiple | closed | 2026-05-01 | 2026-05-07 | stop_hit | -1.316R | 4 | +0.395R | +1.711R | $-49.33 |
| TROX-2026-03-20 | 0.667 | 20 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | stop_hit | -1.316R | 4 | +0.395R | +1.711R | $-49.33 |
| TROX-2026-03-20 | 0.667 | 20 | D_minervini_stage2_progression | closed | 2026-05-01 | 2026-05-07 | stop_hit | -1.316R | 4 | +0.395R | +1.711R | $-49.33 |
| TROX-2026-03-20 | 0.667 | 20 | E_oneil_cup_with_handle_measured_move | closed | 2026-05-01 | 2026-05-07 | stop_hit | -2.027R | 4 | +0.609R | +2.637R | $-76.03 |
| TROX-2026-03-20 | 0.667 | 20 | F_qullamaggie_momentum_burst | closed | 2026-05-01 | 2026-05-07 | stop_hit | -1.316R | 4 | +0.395R | +1.711R | $-49.33 |

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
