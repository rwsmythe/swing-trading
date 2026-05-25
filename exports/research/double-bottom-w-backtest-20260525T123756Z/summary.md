# Double-Bottom-W Walk-Forward Backtest Summary

**Cohort:** composite>=0.7 double_bottom_w; NO RECENCY FILTER (all unique W primaries) (172 unique W patterns)

**Cohort source:** tests\fixtures\research\double_bottom_w_backtest\cohort.json
**Recency filter:** trough_2 within 60 calendar days of asof (172 of 172 verdicts passed).
**Both-exist diagnostic:** 1 ticker-reads hit Shape A + legacy (Shape A wins per OQ-18).

## Per-ruleset aggregate stats

| Ruleset | Patterns | Triggered | Closed | Winners | Losers | Untrig | Open | Win-rate | Avg R win | Avg R loser | Expectancy R closed | Avg sessions held (closed) | Avg sessions held (open) |
|---------|----------|-----------|--------|---------|--------|--------|------|----------|-----------|-------------|---------------------|------------------------|----------------------|
| A_minervini_trail_ma | 172 | 103 | 37 | 0 | 37 | 69 | 66 | 0.0% | n/a | -0.150R | -0.150R | 1.4d | 6.4d |
| B_fixed_R_multiple | 172 | 103 | 0 | 0 | 0 | 69 | 103 | n/a | n/a | n/a | n/a | n/a | 5.4d |
| C_close_below_50d | 172 | 103 | 37 | 0 | 37 | 69 | 66 | 0.0% | n/a | -0.150R | -0.150R | 1.4d | 6.4d |

## Exit-reason breakdown

| Ruleset | stop_hit | trail_stop | target_3R | close_below_50d | open_at_data_tail | untriggered | ohlcv_empty | entry_gap_below_stop |
|---------|----------|------------|-----------|-----------------|-------------------|-------------|-------------|----------------------|
| A_minervini_trail_ma | 0 | 0 | 0 | 37 | 66 | 69 | 0 | 0 |
| B_fixed_R_multiple | 0 | 0 | 0 | 0 | 103 | 69 | 0 | 0 |
| C_close_below_50d | 0 | 0 | 0 | 37 | 66 | 69 | 0 | 0 |

## Per-pattern detail (composite>=0.7; sorted by ticker then trough_1_date)

| pattern_id | composite | days_t2_to_asof | ruleset | status | entry_date | exit_date | exit_reason | R-multiple | sessions_held | peak_R | dd_to_exit_R | pnl_$ |
|------------|-----------|-----------------|---------|--------|------------|-----------|-------------|------------|---------------|--------|--------------|-------|
| DK-2021-06-18 | 0.767 | 1761 | A_minervini_trail_ma | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.118R | 2 | +0.023R | +0.141R | $-4.42 |
| DK-2021-06-18 | 0.767 | 1761 | B_fixed_R_multiple | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | -0.065R | 3 | +0.023R | +0.088R | $-2.42 |
| DK-2021-06-18 | 0.767 | 1761 | C_close_below_50d | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.118R | 2 | +0.023R | +0.141R | $-4.42 |
| DK-2021-11-19 | 0.767 | 1628 | A_minervini_trail_ma | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.115R | 2 | +0.023R | +0.138R | $-4.32 |
| DK-2021-11-19 | 0.767 | 1628 | B_fixed_R_multiple | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | -0.063R | 3 | +0.023R | +0.086R | $-2.37 |
| DK-2021-11-19 | 0.767 | 1628 | C_close_below_50d | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.115R | 2 | +0.023R | +0.138R | $-4.32 |
| DK-2021-11-29 | 0.767 | 1607 | A_minervini_trail_ma | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.113R | 2 | +0.022R | +0.135R | $-4.23 |
| DK-2021-11-29 | 0.767 | 1607 | B_fixed_R_multiple | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | -0.062R | 3 | +0.022R | +0.084R | $-2.32 |
| DK-2021-11-29 | 0.767 | 1607 | C_close_below_50d | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.113R | 2 | +0.022R | +0.135R | $-4.23 |
| DK-2022-05-09 | 0.833 | 1421 | A_minervini_trail_ma | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.168R | 2 | +0.033R | +0.201R | $-6.29 |
| DK-2022-05-09 | 0.833 | 1421 | B_fixed_R_multiple | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | -0.092R | 3 | +0.033R | +0.125R | $-3.45 |
| DK-2022-05-09 | 0.833 | 1421 | C_close_below_50d | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.168R | 2 | +0.033R | +0.201R | $-6.29 |
| DK-2022-10-14 | 0.767 | 1243 | A_minervini_trail_ma | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.175R | 2 | +0.035R | +0.210R | $-6.58 |
| DK-2022-10-14 | 0.767 | 1243 | B_fixed_R_multiple | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | -0.096R | 3 | +0.035R | +0.131R | $-3.61 |
| DK-2022-10-14 | 0.767 | 1243 | C_close_below_50d | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.175R | 2 | +0.035R | +0.210R | $-6.58 |
| DK-2023-03-15 | 0.767 | 1107 | A_minervini_trail_ma | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.134R | 2 | +0.026R | +0.160R | $-5.01 |
| DK-2023-03-15 | 0.767 | 1107 | B_fixed_R_multiple | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | -0.073R | 3 | +0.026R | +0.100R | $-2.75 |
| DK-2023-03-15 | 0.767 | 1107 | C_close_below_50d | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.134R | 2 | +0.026R | +0.160R | $-5.01 |
| DK-2023-08-31 | 0.767 | 952 | A_minervini_trail_ma | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.166R | 2 | +0.033R | +0.199R | $-6.24 |
| DK-2023-08-31 | 0.767 | 952 | B_fixed_R_multiple | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | -0.091R | 3 | +0.033R | +0.124R | $-3.42 |
| DK-2023-08-31 | 0.767 | 952 | C_close_below_50d | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.166R | 2 | +0.033R | +0.199R | $-6.24 |
| DK-2023-10-26 | 0.767 | 918 | A_minervini_trail_ma | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.167R | 2 | +0.033R | +0.200R | $-6.27 |
| DK-2023-10-26 | 0.767 | 918 | B_fixed_R_multiple | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | -0.092R | 3 | +0.033R | +0.125R | $-3.44 |
| DK-2023-10-26 | 0.767 | 918 | C_close_below_50d | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.167R | 2 | +0.033R | +0.200R | $-6.27 |
| DK-2024-08-06 | 0.933 | 613 | A_minervini_trail_ma | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.129R | 2 | +0.026R | +0.155R | $-4.85 |
| DK-2024-08-06 | 0.933 | 613 | B_fixed_R_multiple | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | -0.071R | 3 | +0.026R | +0.097R | $-2.66 |
| DK-2024-08-06 | 0.933 | 613 | C_close_below_50d | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.129R | 2 | +0.026R | +0.155R | $-4.85 |
| DK-2024-09-09 | 0.933 | 590 | A_minervini_trail_ma | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.129R | 2 | +0.025R | +0.155R | $-4.84 |
| DK-2024-09-09 | 0.933 | 590 | B_fixed_R_multiple | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | -0.071R | 3 | +0.025R | +0.096R | $-2.66 |
| DK-2024-09-09 | 0.933 | 590 | C_close_below_50d | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.129R | 2 | +0.025R | +0.155R | $-4.84 |
| DK-2024-11-01 | 0.833 | 511 | A_minervini_trail_ma | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.117R | 2 | +0.023R | +0.141R | $-4.40 |
| DK-2024-11-01 | 0.833 | 511 | B_fixed_R_multiple | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | -0.064R | 3 | +0.023R | +0.088R | $-2.41 |
| DK-2024-11-01 | 0.833 | 511 | C_close_below_50d | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.117R | 2 | +0.023R | +0.141R | $-4.40 |
| DK-2025-03-10 | 0.767 | 402 | A_minervini_trail_ma | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.102R | 2 | +0.020R | +0.123R | $-3.84 |
| DK-2025-03-10 | 0.767 | 402 | B_fixed_R_multiple | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | -0.056R | 3 | +0.020R | +0.076R | $-2.11 |
| DK-2025-03-10 | 0.767 | 402 | C_close_below_50d | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.102R | 2 | +0.020R | +0.123R | $-3.84 |
| DK-2025-06-24 | 0.767 | 282 | A_minervini_trail_ma | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.136R | 2 | +0.027R | +0.163R | $-5.10 |
| DK-2025-06-24 | 0.767 | 282 | B_fixed_R_multiple | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | -0.075R | 3 | +0.027R | +0.101R | $-2.79 |
| DK-2025-06-24 | 0.767 | 282 | C_close_below_50d | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.136R | 2 | +0.027R | +0.163R | $-5.10 |
| DK-2026-01-20 | 0.753 | 92 | A_minervini_trail_ma | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.271R | 2 | +0.053R | +0.325R | $-10.17 |
| DK-2026-01-20 | 0.753 | 92 | B_fixed_R_multiple | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | -0.149R | 3 | +0.053R | +0.202R | $-5.58 |
| DK-2026-01-20 | 0.753 | 92 | C_close_below_50d | closed | 2026-05-19 | 2026-05-21 | close_below_50d | -0.271R | 2 | +0.053R | +0.325R | $-10.17 |
| DK-2026-03-09 | 0.741 | 53 | A_minervini_trail_ma | closed | 2026-05-20 | 2026-05-21 | close_below_50d | -0.960R | 1 | +0.223R | +1.183R | $-35.98 |
| DK-2026-03-09 | 0.741 | 53 | B_fixed_R_multiple | open | 2026-05-20 | 2026-05-22 | open_at_data_tail | -0.483R | 2 | +0.223R | +0.706R | $-18.11 |
| DK-2026-03-09 | 0.741 | 53 | C_close_below_50d | closed | 2026-05-20 | 2026-05-21 | close_below_50d | -0.960R | 1 | +0.223R | +1.183R | $-35.98 |
| DNTH-2025-05-30 | 0.767 | 311 | A_minervini_trail_ma | open | 2026-04-29 | 2026-04-30 | open_at_data_tail | +0.070R | 1 | +0.073R | +0.003R | $+2.62 |
| DNTH-2025-05-30 | 0.767 | 311 | B_fixed_R_multiple | open | 2026-04-29 | 2026-04-30 | open_at_data_tail | +0.070R | 1 | +0.073R | +0.003R | $+2.62 |
| DNTH-2025-05-30 | 0.767 | 311 | C_close_below_50d | open | 2026-04-29 | 2026-04-30 | open_at_data_tail | +0.070R | 1 | +0.073R | +0.003R | $+2.62 |
| DNTH-2025-07-15 | 0.767 | 262 | A_minervini_trail_ma | open | 2026-04-29 | 2026-04-30 | open_at_data_tail | +0.072R | 1 | +0.075R | +0.003R | $+2.70 |
| DNTH-2025-07-15 | 0.767 | 262 | B_fixed_R_multiple | open | 2026-04-29 | 2026-04-30 | open_at_data_tail | +0.072R | 1 | +0.075R | +0.003R | $+2.70 |
| DNTH-2025-07-15 | 0.767 | 262 | C_close_below_50d | open | 2026-04-29 | 2026-04-30 | open_at_data_tail | +0.072R | 1 | +0.075R | +0.003R | $+2.70 |
| DNTH-2026-01-06 | 0.769 | 81 | A_minervini_trail_ma | open | 2026-04-29 | 2026-04-30 | open_at_data_tail | +0.126R | 1 | +0.131R | +0.005R | $+4.71 |
| DNTH-2026-01-06 | 0.769 | 81 | B_fixed_R_multiple | open | 2026-04-29 | 2026-04-30 | open_at_data_tail | +0.126R | 1 | +0.131R | +0.005R | $+4.71 |
| DNTH-2026-01-06 | 0.769 | 81 | C_close_below_50d | open | 2026-04-29 | 2026-04-30 | open_at_data_tail | +0.126R | 1 | +0.131R | +0.005R | $+4.71 |
| DNTH-2026-02-13 | 0.765 | 38 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DNTH-2026-02-13 | 0.765 | 38 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| DNTH-2026-02-13 | 0.765 | 38 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| FRO-2021-05-27 | 0.767 | 1775 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.033R | 10 | +0.121R | +0.088R | $+1.23 |
| FRO-2021-05-27 | 0.767 | 1775 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.033R | 10 | +0.121R | +0.088R | $+1.23 |
| FRO-2021-05-27 | 0.767 | 1775 | C_close_below_50d | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.033R | 10 | +0.121R | +0.088R | $+1.23 |
| FRO-2021-08-20 | 0.767 | 1701 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.032R | 10 | +0.117R | +0.086R | $+1.19 |
| FRO-2021-08-20 | 0.767 | 1701 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.032R | 10 | +0.117R | +0.086R | $+1.19 |
| FRO-2021-08-20 | 0.767 | 1701 | C_close_below_50d | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.032R | 10 | +0.117R | +0.086R | $+1.19 |
| FRO-2021-12-14 | 0.767 | 1555 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.031R | 10 | +0.114R | +0.083R | $+1.16 |
| FRO-2021-12-14 | 0.767 | 1555 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.031R | 10 | +0.114R | +0.083R | $+1.16 |
| FRO-2021-12-14 | 0.767 | 1555 | C_close_below_50d | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.031R | 10 | +0.114R | +0.083R | $+1.16 |
| FRO-2022-06-17 | 0.933 | 1387 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.033R | 10 | +0.121R | +0.088R | $+1.23 |
| FRO-2022-06-17 | 0.933 | 1387 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.033R | 10 | +0.121R | +0.088R | $+1.23 |
| FRO-2022-06-17 | 0.933 | 1387 | C_close_below_50d | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.033R | 10 | +0.121R | +0.088R | $+1.23 |
| FRO-2022-11-10 | 0.767 | 1246 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.039R | 10 | +0.146R | +0.106R | $+1.48 |
| FRO-2022-11-10 | 0.767 | 1246 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.039R | 10 | +0.146R | +0.106R | $+1.48 |
| FRO-2022-11-10 | 0.767 | 1246 | C_close_below_50d | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.039R | 10 | +0.146R | +0.106R | $+1.48 |
| FRO-2022-12-07 | 0.767 | 1210 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.036R | 10 | +0.133R | +0.097R | $+1.35 |
| FRO-2022-12-07 | 0.767 | 1210 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.036R | 10 | +0.133R | +0.097R | $+1.35 |
| FRO-2022-12-07 | 0.767 | 1210 | C_close_below_50d | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.036R | 10 | +0.133R | +0.097R | $+1.35 |
| FRO-2023-03-16 | 0.767 | 1121 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.043R | 10 | +0.159R | +0.116R | $+1.61 |
| FRO-2023-03-16 | 0.767 | 1121 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.043R | 10 | +0.159R | +0.116R | $+1.61 |
| FRO-2023-03-16 | 0.767 | 1121 | C_close_below_50d | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.043R | 10 | +0.159R | +0.116R | $+1.61 |
| FRO-2023-06-05 | 0.933 | 1036 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.040R | 10 | +0.148R | +0.108R | $+1.50 |
| FRO-2023-06-05 | 0.933 | 1036 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.040R | 10 | +0.148R | +0.108R | $+1.50 |
| FRO-2023-06-05 | 0.933 | 1036 | C_close_below_50d | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.040R | 10 | +0.148R | +0.108R | $+1.50 |
| FRO-2024-06-17 | 0.767 | 657 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.071R | 10 | +0.261R | +0.190R | $+2.65 |
| FRO-2024-06-17 | 0.767 | 657 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.071R | 10 | +0.261R | +0.190R | $+2.65 |
| FRO-2024-06-17 | 0.767 | 657 | C_close_below_50d | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.071R | 10 | +0.261R | +0.190R | $+2.65 |
| FRO-2024-07-10 | 0.767 | 631 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.065R | 10 | +0.239R | +0.175R | $+2.43 |
| FRO-2024-07-10 | 0.767 | 631 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.065R | 10 | +0.239R | +0.175R | $+2.43 |
| FRO-2024-07-10 | 0.767 | 631 | C_close_below_50d | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.065R | 10 | +0.239R | +0.175R | $+2.43 |
| FRO-2024-08-05 | 0.767 | 595 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.063R | 10 | +0.233R | +0.170R | $+2.37 |
| FRO-2024-08-05 | 0.767 | 595 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.063R | 10 | +0.233R | +0.170R | $+2.37 |
| FRO-2024-08-05 | 0.767 | 595 | C_close_below_50d | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.063R | 10 | +0.233R | +0.170R | $+2.37 |
| FRO-2024-09-10 | 0.767 | 580 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.062R | 10 | +0.228R | +0.166R | $+2.31 |
| FRO-2024-09-10 | 0.767 | 580 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.062R | 10 | +0.228R | +0.166R | $+2.31 |
| FRO-2024-09-10 | 0.767 | 580 | C_close_below_50d | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.062R | 10 | +0.228R | +0.166R | $+2.31 |
| FRO-2025-01-27 | 0.933 | 425 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.044R | 10 | +0.162R | +0.118R | $+1.64 |
| FRO-2025-01-27 | 0.933 | 425 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.044R | 10 | +0.162R | +0.118R | $+1.64 |
| FRO-2025-01-27 | 0.933 | 425 | C_close_below_50d | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.044R | 10 | +0.162R | +0.118R | $+1.64 |
| FRO-2025-02-27 | 0.767 | 414 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.043R | 10 | +0.161R | +0.117R | $+1.63 |
| FRO-2025-02-27 | 0.767 | 414 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.043R | 10 | +0.161R | +0.117R | $+1.63 |
| FRO-2025-02-27 | 0.767 | 414 | C_close_below_50d | open | 2026-04-30 | 2026-05-14 | open_at_data_tail | +0.043R | 10 | +0.161R | +0.117R | $+1.63 |
| KOD-2023-03-24 | 0.767 | 1117 | A_minervini_trail_ma | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.081R | 4 | +0.085R | +0.166R | $-3.03 |
| KOD-2023-03-24 | 0.767 | 1117 | B_fixed_R_multiple | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.081R | 4 | +0.085R | +0.166R | $-3.03 |
| KOD-2023-03-24 | 0.767 | 1117 | C_close_below_50d | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.081R | 4 | +0.085R | +0.166R | $-3.03 |
| KOD-2023-06-29 | 0.767 | 1019 | A_minervini_trail_ma | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.085R | 4 | +0.089R | +0.174R | $-3.18 |
| KOD-2023-06-29 | 0.767 | 1019 | B_fixed_R_multiple | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.085R | 4 | +0.089R | +0.174R | $-3.18 |
| KOD-2023-06-29 | 0.767 | 1019 | C_close_below_50d | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.085R | 4 | +0.089R | +0.174R | $-3.18 |
| KOD-2024-03-19 | 0.767 | 757 | A_minervini_trail_ma | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.080R | 4 | +0.084R | +0.163R | $-2.99 |
| KOD-2024-03-19 | 0.767 | 757 | B_fixed_R_multiple | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.080R | 4 | +0.084R | +0.163R | $-2.99 |
| KOD-2024-03-19 | 0.767 | 757 | C_close_below_50d | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.080R | 4 | +0.084R | +0.163R | $-2.99 |
| KOD-2024-04-25 | 0.767 | 702 | A_minervini_trail_ma | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.077R | 4 | +0.081R | +0.159R | $-2.90 |
| KOD-2024-04-25 | 0.767 | 702 | B_fixed_R_multiple | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.077R | 4 | +0.081R | +0.159R | $-2.90 |
| KOD-2024-04-25 | 0.767 | 702 | C_close_below_50d | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.077R | 4 | +0.081R | +0.159R | $-2.90 |
| KOD-2024-08-07 | 0.933 | 602 | A_minervini_trail_ma | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.076R | 4 | +0.080R | +0.156R | $-2.86 |
| KOD-2024-08-07 | 0.933 | 602 | B_fixed_R_multiple | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.076R | 4 | +0.080R | +0.156R | $-2.86 |
| KOD-2024-08-07 | 0.933 | 602 | C_close_below_50d | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.076R | 4 | +0.080R | +0.156R | $-2.86 |
| KOD-2025-05-15 | 0.833 | 335 | A_minervini_trail_ma | open | 2026-05-04 | 2026-05-11 | open_at_data_tail | -0.088R | 5 | +0.080R | +0.168R | $-3.32 |
| KOD-2025-05-15 | 0.833 | 335 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-11 | open_at_data_tail | -0.088R | 5 | +0.080R | +0.168R | $-3.32 |
| KOD-2025-05-15 | 0.833 | 335 | C_close_below_50d | open | 2026-05-04 | 2026-05-11 | open_at_data_tail | -0.088R | 5 | +0.080R | +0.168R | $-3.32 |
| KOD-2025-05-30 | 0.833 | 317 | A_minervini_trail_ma | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.079R | 4 | +0.082R | +0.161R | $-2.95 |
| KOD-2025-05-30 | 0.833 | 317 | B_fixed_R_multiple | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.079R | 4 | +0.082R | +0.161R | $-2.95 |
| KOD-2025-05-30 | 0.833 | 317 | C_close_below_50d | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.079R | 4 | +0.082R | +0.161R | $-2.95 |
| KOD-2025-10-23 | 0.767 | 176 | A_minervini_trail_ma | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.118R | 4 | +0.124R | +0.242R | $-4.43 |
| KOD-2025-10-23 | 0.767 | 176 | B_fixed_R_multiple | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.118R | 4 | +0.124R | +0.242R | $-4.43 |
| KOD-2025-10-23 | 0.767 | 176 | C_close_below_50d | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.118R | 4 | +0.124R | +0.242R | $-4.43 |
| KOD-2026-01-05 | 0.839 | 85 | A_minervini_trail_ma | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.140R | 4 | +0.147R | +0.287R | $-5.25 |
| KOD-2026-01-05 | 0.839 | 85 | B_fixed_R_multiple | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.140R | 4 | +0.147R | +0.287R | $-5.25 |
| KOD-2026-01-05 | 0.839 | 85 | C_close_below_50d | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.140R | 4 | +0.147R | +0.287R | $-5.25 |
| KOD-2026-02-05 | 0.857 | 38 | A_minervini_trail_ma | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.145R | 4 | +0.152R | +0.298R | $-5.45 |
| KOD-2026-02-05 | 0.857 | 38 | B_fixed_R_multiple | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.145R | 4 | +0.152R | +0.298R | $-5.45 |
| KOD-2026-02-05 | 0.857 | 38 | C_close_below_50d | open | 2026-05-05 | 2026-05-11 | open_at_data_tail | -0.145R | 4 | +0.152R | +0.298R | $-5.45 |
| NAT-2022-06-02 | 0.767 | 1429 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.030R | 0 | +0.003R | +0.033R | $-1.12 |
| NAT-2022-06-02 | 0.767 | 1429 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-14 | open_at_data_tail | -0.030R | 0 | +0.003R | +0.033R | $-1.12 |
| NAT-2022-06-02 | 0.767 | 1429 | C_close_below_50d | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.030R | 0 | +0.003R | +0.033R | $-1.12 |
| NAT-2022-06-17 | 0.767 | 1406 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.029R | 0 | +0.003R | +0.032R | $-1.09 |
| NAT-2022-06-17 | 0.767 | 1406 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-14 | open_at_data_tail | -0.029R | 0 | +0.003R | +0.032R | $-1.09 |
| NAT-2022-06-17 | 0.767 | 1406 | C_close_below_50d | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.029R | 0 | +0.003R | +0.032R | $-1.09 |
| NAT-2022-12-07 | 0.933 | 1224 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.040R | 0 | +0.004R | +0.044R | $-1.50 |
| NAT-2022-12-07 | 0.933 | 1224 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-14 | open_at_data_tail | -0.040R | 0 | +0.004R | +0.044R | $-1.50 |
| NAT-2022-12-07 | 0.933 | 1224 | C_close_below_50d | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.040R | 0 | +0.004R | +0.044R | $-1.50 |
| NAT-2023-01-04 | 0.933 | 1202 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.040R | 0 | +0.004R | +0.043R | $-1.50 |
| NAT-2023-01-04 | 0.933 | 1202 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-14 | open_at_data_tail | -0.040R | 0 | +0.004R | +0.043R | $-1.50 |
| NAT-2023-01-04 | 0.933 | 1202 | C_close_below_50d | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.040R | 0 | +0.004R | +0.043R | $-1.50 |
| NAT-2023-05-31 | 0.767 | 1049 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.051R | 0 | +0.005R | +0.055R | $-1.91 |
| NAT-2023-05-31 | 0.767 | 1049 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-14 | open_at_data_tail | -0.051R | 0 | +0.005R | +0.055R | $-1.91 |
| NAT-2023-05-31 | 0.767 | 1049 | C_close_below_50d | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.051R | 0 | +0.005R | +0.055R | $-1.91 |
| NAT-2024-03-20 | 0.767 | 750 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.058R | 0 | +0.005R | +0.063R | $-2.17 |
| NAT-2024-03-20 | 0.767 | 750 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-14 | open_at_data_tail | -0.058R | 0 | +0.005R | +0.063R | $-2.17 |
| NAT-2024-03-20 | 0.767 | 750 | C_close_below_50d | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.058R | 0 | +0.005R | +0.063R | $-2.17 |
| NAT-2024-06-17 | 0.767 | 663 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.056R | 0 | +0.005R | +0.061R | $-2.10 |
| NAT-2024-06-17 | 0.767 | 663 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-14 | open_at_data_tail | -0.056R | 0 | +0.005R | +0.061R | $-2.10 |
| NAT-2024-06-17 | 0.767 | 663 | C_close_below_50d | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.056R | 0 | +0.005R | +0.061R | $-2.10 |
| NAT-2025-11-04 | 0.767 | 144 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.048R | 0 | +0.004R | +0.053R | $-1.81 |
| NAT-2025-11-04 | 0.767 | 144 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-14 | open_at_data_tail | -0.048R | 0 | +0.004R | +0.053R | $-1.81 |
| NAT-2025-11-04 | 0.767 | 144 | C_close_below_50d | closed | 2026-05-14 | 2026-05-14 | close_below_50d | -0.048R | 0 | +0.004R | +0.053R | $-1.81 |
| OII-2026-03-13 | 0.833 | 20 | A_minervini_trail_ma | open | 2026-04-23 | 2026-04-27 | open_at_data_tail | +0.780R | 2 | +1.740R | +0.960R | $+29.26 |
| OII-2026-03-13 | 0.833 | 20 | B_fixed_R_multiple | open | 2026-04-23 | 2026-04-27 | open_at_data_tail | +0.780R | 2 | +1.740R | +0.960R | $+29.26 |
| OII-2026-03-13 | 0.833 | 20 | C_close_below_50d | open | 2026-04-23 | 2026-04-27 | open_at_data_tail | +0.780R | 2 | +1.740R | +0.960R | $+29.26 |
| PTEN-2023-05-16 | 0.767 | 1073 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.132R | 8 | +0.458R | +0.327R | $+4.93 |
| PTEN-2023-05-16 | 0.767 | 1073 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.132R | 8 | +0.458R | +0.327R | $+4.93 |
| PTEN-2023-05-16 | 0.767 | 1073 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.132R | 8 | +0.458R | +0.327R | $+4.93 |
| PTEN-2024-01-17 | 0.833 | 823 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.159R | 8 | +0.553R | +0.395R | $+5.96 |
| PTEN-2024-01-17 | 0.833 | 823 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.159R | 8 | +0.553R | +0.395R | $+5.96 |
| PTEN-2024-01-17 | 0.833 | 823 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.159R | 8 | +0.553R | +0.395R | $+5.96 |
| PTEN-2024-07-08 | 0.833 | 653 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.143R | 8 | +0.498R | +0.355R | $+5.36 |
| PTEN-2024-07-08 | 0.833 | 653 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.143R | 8 | +0.498R | +0.355R | $+5.36 |
| PTEN-2024-07-08 | 0.833 | 653 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.143R | 8 | +0.498R | +0.355R | $+5.36 |
| PTEN-2024-09-26 | 0.767 | 553 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.067R | 8 | +0.232R | +0.165R | $+2.50 |
| PTEN-2024-09-26 | 0.767 | 553 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.067R | 8 | +0.232R | +0.165R | $+2.50 |
| PTEN-2024-09-26 | 0.767 | 553 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.067R | 8 | +0.232R | +0.165R | $+2.50 |
| PTEN-2025-02-03 | 0.767 | 428 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.063R | 8 | +0.219R | +0.156R | $+2.36 |
| PTEN-2025-02-03 | 0.767 | 428 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.063R | 8 | +0.219R | +0.156R | $+2.36 |
| PTEN-2025-02-03 | 0.767 | 428 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.063R | 8 | +0.219R | +0.156R | $+2.36 |
| PTEN-2025-03-06 | 0.767 | 395 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.047R | 8 | +0.164R | +0.117R | $+1.76 |
| PTEN-2025-03-06 | 0.767 | 395 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.047R | 8 | +0.164R | +0.117R | $+1.76 |
| PTEN-2025-03-06 | 0.767 | 395 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.047R | 8 | +0.164R | +0.117R | $+1.76 |
| PTEN-2025-04-10 | 0.833 | 373 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.048R | 8 | +0.168R | +0.120R | $+1.81 |
| PTEN-2025-04-10 | 0.833 | 373 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.048R | 8 | +0.168R | +0.120R | $+1.81 |
| PTEN-2025-04-10 | 0.833 | 373 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.048R | 8 | +0.168R | +0.120R | $+1.81 |
| PTEN-2025-05-06 | 0.767 | 340 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.047R | 8 | +0.165R | +0.118R | $+1.78 |
| PTEN-2025-05-06 | 0.767 | 340 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.047R | 8 | +0.165R | +0.118R | $+1.78 |
| PTEN-2025-05-06 | 0.767 | 340 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.047R | 8 | +0.165R | +0.118R | $+1.78 |
| PTEN-2025-08-20 | 0.933 | 220 | A_minervini_trail_ma | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.045R | 8 | +0.157R | +0.112R | $+1.69 |
| PTEN-2025-08-20 | 0.933 | 220 | B_fixed_R_multiple | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.045R | 8 | +0.157R | +0.112R | $+1.69 |
| PTEN-2025-08-20 | 0.933 | 220 | C_close_below_50d | open | 2026-05-12 | 2026-05-22 | open_at_data_tail | +0.045R | 8 | +0.157R | +0.112R | $+1.69 |
| RLMD-2021-10-27 | 0.767 | 1621 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RLMD-2021-10-27 | 0.767 | 1621 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RLMD-2021-10-27 | 0.767 | 1621 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RLMD-2021-12-03 | 0.933 | 1559 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RLMD-2021-12-03 | 0.933 | 1559 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RLMD-2021-12-03 | 0.933 | 1559 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RLMD-2022-05-12 | 0.767 | 1436 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RLMD-2022-05-12 | 0.767 | 1436 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RLMD-2022-05-12 | 0.767 | 1436 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RLMD-2023-03-24 | 0.767 | 1133 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.110R | 1 | +0.011R | +0.121R | $-4.12 |
| RLMD-2023-03-24 | 0.767 | 1133 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.083R | 6 | +0.011R | +0.095R | $-3.12 |
| RLMD-2023-03-24 | 0.767 | 1133 | C_close_below_50d | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.110R | 1 | +0.011R | +0.121R | $-4.12 |
| RLMD-2023-05-16 | 0.767 | 1062 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.117R | 1 | +0.012R | +0.129R | $-4.39 |
| RLMD-2023-05-16 | 0.767 | 1062 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.089R | 6 | +0.012R | +0.101R | $-3.33 |
| RLMD-2023-05-16 | 0.767 | 1062 | C_close_below_50d | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.117R | 1 | +0.012R | +0.129R | $-4.39 |
| RLMD-2023-06-15 | 0.767 | 1050 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.114R | 1 | +0.012R | +0.126R | $-4.28 |
| RLMD-2023-06-15 | 0.767 | 1050 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.087R | 6 | +0.012R | +0.098R | $-3.25 |
| RLMD-2023-06-15 | 0.767 | 1050 | C_close_below_50d | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.114R | 1 | +0.012R | +0.126R | $-4.28 |
| RLMD-2023-06-27 | 0.833 | 1020 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.115R | 1 | +0.012R | +0.127R | $-4.33 |
| RLMD-2023-06-27 | 0.833 | 1020 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.088R | 6 | +0.012R | +0.100R | $-3.28 |
| RLMD-2023-06-27 | 0.833 | 1020 | C_close_below_50d | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.115R | 1 | +0.012R | +0.127R | $-4.33 |
| RLMD-2023-08-17 | 0.933 | 966 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.123R | 1 | +0.013R | +0.136R | $-4.61 |
| RLMD-2023-08-17 | 0.933 | 966 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.093R | 6 | +0.013R | +0.106R | $-3.50 |
| RLMD-2023-08-17 | 0.933 | 966 | C_close_below_50d | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.123R | 1 | +0.013R | +0.136R | $-4.61 |
| RLMD-2024-11-26 | 0.767 | 510 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.081R | 1 | +0.008R | +0.090R | $-3.05 |
| RLMD-2024-11-26 | 0.767 | 510 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.062R | 6 | +0.008R | +0.070R | $-2.31 |
| RLMD-2024-11-26 | 0.767 | 510 | C_close_below_50d | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.081R | 1 | +0.008R | +0.090R | $-3.05 |
| RLMD-2024-12-18 | 0.767 | 463 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.081R | 1 | +0.008R | +0.090R | $-3.04 |
| RLMD-2024-12-18 | 0.767 | 463 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.062R | 6 | +0.008R | +0.070R | $-2.31 |
| RLMD-2024-12-18 | 0.767 | 463 | C_close_below_50d | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.081R | 1 | +0.008R | +0.090R | $-3.04 |
| RLMD-2025-06-30 | 0.767 | 298 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.084R | 1 | +0.009R | +0.093R | $-3.15 |
| RLMD-2025-06-30 | 0.767 | 298 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.064R | 6 | +0.009R | +0.072R | $-2.39 |
| RLMD-2025-06-30 | 0.767 | 298 | C_close_below_50d | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.084R | 1 | +0.009R | +0.093R | $-3.15 |
| RLMD-2025-07-18 | 0.767 | 274 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.084R | 1 | +0.009R | +0.092R | $-3.14 |
| RLMD-2025-07-18 | 0.767 | 274 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.064R | 6 | +0.009R | +0.072R | $-2.38 |
| RLMD-2025-07-18 | 0.767 | 274 | C_close_below_50d | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.084R | 1 | +0.009R | +0.092R | $-3.14 |
| RLMD-2026-01-16 | 0.820 | 102 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.146R | 1 | +0.015R | +0.161R | $-5.48 |
| RLMD-2026-01-16 | 0.820 | 102 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.111R | 6 | +0.015R | +0.126R | $-4.16 |
| RLMD-2026-01-16 | 0.820 | 102 | C_close_below_50d | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.146R | 1 | +0.015R | +0.161R | $-5.48 |
| RLMD-2026-01-30 | 0.769 | 84 | A_minervini_trail_ma | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.150R | 1 | +0.015R | +0.165R | $-5.61 |
| RLMD-2026-01-30 | 0.769 | 84 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.114R | 6 | +0.015R | +0.129R | $-4.26 |
| RLMD-2026-01-30 | 0.769 | 84 | C_close_below_50d | closed | 2026-05-14 | 2026-05-15 | close_below_50d | -0.150R | 1 | +0.015R | +0.165R | $-5.61 |
| RNG-2021-12-16 | 0.767 | 1574 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RNG-2021-12-16 | 0.767 | 1574 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RNG-2021-12-16 | 0.767 | 1574 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RNG-2022-01-27 | 0.767 | 1547 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RNG-2022-01-27 | 0.767 | 1547 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RNG-2022-01-27 | 0.767 | 1547 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RNG-2022-05-24 | 0.767 | 1415 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RNG-2022-05-24 | 0.767 | 1415 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RNG-2022-05-24 | 0.767 | 1415 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RNG-2022-06-30 | 0.767 | 1385 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RNG-2022-06-30 | 0.767 | 1385 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RNG-2022-06-30 | 0.767 | 1385 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RNG-2022-07-14 | 0.833 | 1368 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RNG-2022-07-14 | 0.833 | 1368 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RNG-2022-07-14 | 0.833 | 1368 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| RNG-2022-08-29 | 0.767 | 1305 | A_minervini_trail_ma | open | 2026-05-05 | 2026-05-12 | open_at_data_tail | -0.684R | 5 | +0.145R | +0.828R | $-25.64 |
| RNG-2022-08-29 | 0.767 | 1305 | B_fixed_R_multiple | open | 2026-05-05 | 2026-05-12 | open_at_data_tail | -0.684R | 5 | +0.145R | +0.828R | $-25.64 |
| RNG-2022-08-29 | 0.767 | 1305 | C_close_below_50d | open | 2026-05-05 | 2026-05-12 | open_at_data_tail | -0.684R | 5 | +0.145R | +0.828R | $-25.64 |
| RNG-2022-11-22 | 0.833 | 1240 | A_minervini_trail_ma | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.335R | 6 | +0.313R | +0.648R | $-12.54 |
| RNG-2022-11-22 | 0.833 | 1240 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.335R | 6 | +0.313R | +0.648R | $-12.54 |
| RNG-2022-11-22 | 0.833 | 1240 | C_close_below_50d | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.335R | 6 | +0.313R | +0.648R | $-12.54 |
| RNG-2023-06-09 | 0.767 | 1042 | A_minervini_trail_ma | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.255R | 6 | +0.239R | +0.493R | $-9.55 |
| RNG-2023-06-09 | 0.767 | 1042 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.255R | 6 | +0.239R | +0.493R | $-9.55 |
| RNG-2023-06-09 | 0.767 | 1042 | C_close_below_50d | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.255R | 6 | +0.239R | +0.493R | $-9.55 |
| RNG-2023-09-21 | 0.767 | 916 | A_minervini_trail_ma | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.171R | 6 | +0.160R | +0.330R | $-6.40 |
| RNG-2023-09-21 | 0.767 | 916 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.171R | 6 | +0.160R | +0.330R | $-6.40 |
| RNG-2023-09-21 | 0.767 | 916 | C_close_below_50d | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.171R | 6 | +0.160R | +0.330R | $-6.40 |
| RNG-2023-10-27 | 0.833 | 899 | A_minervini_trail_ma | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.180R | 6 | +0.168R | +0.348R | $-6.74 |
| RNG-2023-10-27 | 0.833 | 899 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.180R | 6 | +0.168R | +0.348R | $-6.74 |
| RNG-2023-10-27 | 0.833 | 899 | C_close_below_50d | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.180R | 6 | +0.168R | +0.348R | $-6.74 |
| RNG-2023-12-12 | 0.767 | 848 | A_minervini_trail_ma | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.236R | 6 | +0.221R | +0.458R | $-8.86 |
| RNG-2023-12-12 | 0.767 | 848 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.236R | 6 | +0.221R | +0.458R | $-8.86 |
| RNG-2023-12-12 | 0.767 | 848 | C_close_below_50d | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.236R | 6 | +0.221R | +0.458R | $-8.86 |
| RNG-2024-01-03 | 0.767 | 798 | A_minervini_trail_ma | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.224R | 6 | +0.210R | +0.435R | $-8.42 |
| RNG-2024-01-03 | 0.767 | 798 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.224R | 6 | +0.210R | +0.435R | $-8.42 |
| RNG-2024-01-03 | 0.767 | 798 | C_close_below_50d | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.224R | 6 | +0.210R | +0.435R | $-8.42 |
| RNG-2024-02-22 | 0.767 | 742 | A_minervini_trail_ma | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.211R | 6 | +0.198R | +0.409R | $-7.92 |
| RNG-2024-02-22 | 0.767 | 742 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.211R | 6 | +0.198R | +0.409R | $-7.92 |
| RNG-2024-02-22 | 0.767 | 742 | C_close_below_50d | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.211R | 6 | +0.198R | +0.409R | $-7.92 |
| RNG-2025-08-11 | 0.767 | 202 | A_minervini_trail_ma | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.180R | 6 | +0.169R | +0.349R | $-6.76 |
| RNG-2025-08-11 | 0.767 | 202 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.180R | 6 | +0.169R | +0.349R | $-6.76 |
| RNG-2025-08-11 | 0.767 | 202 | C_close_below_50d | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.180R | 6 | +0.169R | +0.349R | $-6.76 |
| RNG-2025-10-10 | 0.933 | 161 | A_minervini_trail_ma | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.178R | 6 | +0.166R | +0.344R | $-6.66 |
| RNG-2025-10-10 | 0.933 | 161 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.178R | 6 | +0.166R | +0.344R | $-6.66 |
| RNG-2025-10-10 | 0.933 | 161 | C_close_below_50d | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.178R | 6 | +0.166R | +0.344R | $-6.66 |
| RNG-2026-01-02 | 0.718 | 86 | A_minervini_trail_ma | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.167R | 6 | +0.156R | +0.323R | $-6.25 |
| RNG-2026-01-02 | 0.718 | 86 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.167R | 6 | +0.156R | +0.323R | $-6.25 |
| RNG-2026-01-02 | 0.718 | 86 | C_close_below_50d | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.167R | 6 | +0.156R | +0.323R | $-6.25 |
| RNG-2026-02-03 | 0.868 | 62 | A_minervini_trail_ma | open | 2026-04-30 | 2026-05-12 | open_at_data_tail | +0.405R | 8 | +1.622R | +1.217R | $+15.19 |
| RNG-2026-02-03 | 0.868 | 62 | B_fixed_R_multiple | open | 2026-04-30 | 2026-05-12 | open_at_data_tail | +0.405R | 8 | +1.622R | +1.217R | $+15.19 |
| RNG-2026-02-03 | 0.868 | 62 | C_close_below_50d | open | 2026-04-30 | 2026-05-12 | open_at_data_tail | +0.405R | 8 | +1.622R | +1.217R | $+15.19 |
| RNG-2026-03-27 | 0.767 | 20 | A_minervini_trail_ma | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.284R | 6 | +0.266R | +0.550R | $-10.66 |
| RNG-2026-03-27 | 0.767 | 20 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.284R | 6 | +0.266R | +0.550R | $-10.66 |
| RNG-2026-03-27 | 0.767 | 20 | C_close_below_50d | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.284R | 6 | +0.266R | +0.550R | $-10.66 |
| TROX-2021-12-20 | 0.833 | 1552 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2021-12-20 | 0.833 | 1552 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2021-12-20 | 0.833 | 1552 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-01-28 | 0.767 | 1513 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-01-28 | 0.767 | 1513 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-01-28 | 0.767 | 1513 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-04-29 | 0.933 | 1448 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-04-29 | 0.933 | 1448 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-04-29 | 0.933 | 1448 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-05-12 | 0.767 | 1406 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-05-12 | 0.767 | 1406 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-05-12 | 0.767 | 1406 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-06-23 | 0.767 | 1385 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-06-23 | 0.767 | 1385 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-06-23 | 0.767 | 1385 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-07-14 | 0.767 | 1359 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-07-14 | 0.767 | 1359 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-07-14 | 0.767 | 1359 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-11-21 | 0.767 | 1226 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-11-21 | 0.767 | 1226 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2022-11-21 | 0.767 | 1226 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2023-02-24 | 0.767 | 1141 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2023-02-24 | 0.767 | 1141 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2023-02-24 | 0.767 | 1141 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2023-03-15 | 0.767 | 1099 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2023-03-15 | 0.767 | 1099 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2023-03-15 | 0.767 | 1099 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2023-05-16 | 0.767 | 1064 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2023-05-16 | 0.767 | 1064 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2023-05-16 | 0.767 | 1064 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2024-09-10 | 0.767 | 531 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2024-09-10 | 0.767 | 531 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2024-09-10 | 0.767 | 531 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TROX-2025-05-07 | 0.933 | 341 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.304R | 4 | +0.091R | +0.396R | $-11.41 |
| TROX-2025-05-07 | 0.933 | 341 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-11 | open_at_data_tail | -0.134R | 6 | +0.091R | +0.226R | $-5.04 |
| TROX-2025-05-07 | 0.933 | 341 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.304R | 4 | +0.091R | +0.396R | $-11.41 |
| TROX-2025-06-30 | 0.767 | 264 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.235R | 4 | +0.071R | +0.305R | $-8.81 |
| TROX-2025-06-30 | 0.767 | 264 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-11 | open_at_data_tail | -0.104R | 6 | +0.071R | +0.174R | $-3.89 |
| TROX-2025-06-30 | 0.767 | 264 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.235R | 4 | +0.071R | +0.305R | $-8.81 |
| TROX-2026-02-20 | 0.834 | 54 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.456R | 4 | +0.137R | +0.593R | $-17.10 |
| TROX-2026-02-20 | 0.834 | 54 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-11 | open_at_data_tail | -0.201R | 6 | +0.137R | +0.338R | $-7.55 |
| TROX-2026-02-20 | 0.834 | 54 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.456R | 4 | +0.137R | +0.593R | $-17.10 |
| TSHA-2022-02-23 | 0.767 | 1531 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2022-02-23 | 0.767 | 1531 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2022-02-23 | 0.767 | 1531 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2022-03-28 | 0.767 | 1475 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2022-03-28 | 0.767 | 1475 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2022-03-28 | 0.767 | 1475 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2022-07-29 | 0.767 | 1371 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2022-07-29 | 0.767 | 1371 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2022-07-29 | 0.767 | 1371 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2022-09-07 | 0.767 | 1325 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2022-09-07 | 0.767 | 1325 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2022-09-07 | 0.767 | 1325 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2022-12-07 | 0.767 | 1233 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2022-12-07 | 0.767 | 1233 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2022-12-07 | 0.767 | 1233 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2023-04-10 | 0.767 | 1114 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2023-04-10 | 0.767 | 1114 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2023-04-10 | 0.767 | 1114 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2023-12-20 | 0.833 | 846 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2023-12-20 | 0.833 | 846 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2023-12-20 | 0.833 | 846 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2024-04-04 | 0.767 | 754 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2024-04-04 | 0.767 | 754 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2024-04-04 | 0.767 | 754 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2024-06-26 | 0.767 | 646 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2024-06-26 | 0.767 | 646 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2024-06-26 | 0.767 | 646 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2024-08-05 | 0.833 | 614 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2024-08-05 | 0.833 | 614 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2024-08-05 | 0.833 | 614 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2025-05-28 | 0.933 | 317 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2025-05-28 | 0.933 | 317 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2025-05-28 | 0.933 | 317 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2026-01-16 | 0.843 | 97 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2026-01-16 | 0.843 | 97 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2026-01-16 | 0.843 | 97 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2026-02-05 | 0.733 | 50 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2026-02-05 | 0.733 | 50 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2026-02-05 | 0.733 | 50 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2026-03-24 | 0.767 | 47 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2026-03-24 | 0.767 | 47 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| TSHA-2026-03-24 | 0.767 | 47 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| UCTT-2021-07-16 | 0.767 | 1727 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.024R | 6 | +0.075R | +0.098R | $-0.88 |
| UCTT-2021-07-16 | 0.767 | 1727 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.024R | 6 | +0.075R | +0.098R | $-0.88 |
| UCTT-2021-07-16 | 0.767 | 1727 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.024R | 6 | +0.075R | +0.098R | $-0.88 |
| UCTT-2021-08-19 | 0.833 | 1679 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.024R | 6 | +0.077R | +0.101R | $-0.91 |
| UCTT-2021-08-19 | 0.833 | 1679 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.024R | 6 | +0.077R | +0.101R | $-0.91 |
| UCTT-2021-08-19 | 0.833 | 1679 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.024R | 6 | +0.077R | +0.101R | $-0.91 |
| UCTT-2021-12-20 | 0.767 | 1566 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.027R | 6 | +0.085R | +0.111R | $-1.01 |
| UCTT-2021-12-20 | 0.767 | 1566 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.027R | 6 | +0.085R | +0.111R | $-1.01 |
| UCTT-2021-12-20 | 0.767 | 1566 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.027R | 6 | +0.085R | +0.111R | $-1.01 |
| UCTT-2022-05-11 | 0.767 | 1426 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.019R | 6 | +0.059R | +0.078R | $-0.71 |
| UCTT-2022-05-11 | 0.767 | 1426 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.019R | 6 | +0.059R | +0.078R | $-0.71 |
| UCTT-2022-05-11 | 0.767 | 1426 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.019R | 6 | +0.059R | +0.078R | $-0.71 |
| UCTT-2022-06-16 | 0.767 | 1411 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.019R | 6 | +0.058R | +0.077R | $-0.69 |
| UCTT-2022-06-16 | 0.767 | 1411 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.019R | 6 | +0.058R | +0.077R | $-0.69 |
| UCTT-2022-06-16 | 0.767 | 1411 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.019R | 6 | +0.058R | +0.077R | $-0.69 |
| UCTT-2022-09-26 | 0.767 | 1306 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.018R | 6 | +0.056R | +0.074R | $-0.67 |
| UCTT-2022-09-26 | 0.767 | 1306 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.018R | 6 | +0.056R | +0.074R | $-0.67 |
| UCTT-2022-09-26 | 0.767 | 1306 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.018R | 6 | +0.056R | +0.074R | $-0.67 |
| UCTT-2022-12-28 | 0.933 | 1217 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.020R | 6 | +0.064R | +0.084R | $-0.76 |
| UCTT-2022-12-28 | 0.933 | 1217 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.020R | 6 | +0.064R | +0.084R | $-0.76 |
| UCTT-2022-12-28 | 0.933 | 1217 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.020R | 6 | +0.064R | +0.084R | $-0.76 |
| UCTT-2024-09-09 | 0.833 | 558 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.021R | 6 | +0.066R | +0.086R | $-0.78 |
| UCTT-2024-09-09 | 0.833 | 558 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.021R | 6 | +0.066R | +0.086R | $-0.78 |
| UCTT-2024-09-09 | 0.833 | 558 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.021R | 6 | +0.066R | +0.086R | $-0.78 |
| UCTT-2024-10-31 | 0.833 | 543 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.021R | 6 | +0.066R | +0.087R | $-0.79 |
| UCTT-2024-10-31 | 0.833 | 543 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.021R | 6 | +0.066R | +0.087R | $-0.79 |
| UCTT-2024-10-31 | 0.833 | 543 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.021R | 6 | +0.066R | +0.087R | $-0.79 |
| UCTT-2024-12-19 | 0.767 | 470 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.021R | 6 | +0.066R | +0.087R | $-0.78 |
| UCTT-2024-12-19 | 0.767 | 470 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.021R | 6 | +0.066R | +0.087R | $-0.78 |
| UCTT-2024-12-19 | 0.767 | 470 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.021R | 6 | +0.066R | +0.087R | $-0.78 |
| UCTT-2025-04-17 | 0.833 | 376 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.016R | 6 | +0.051R | +0.067R | $-0.61 |
| UCTT-2025-04-17 | 0.833 | 376 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.016R | 6 | +0.051R | +0.067R | $-0.61 |
| UCTT-2025-04-17 | 0.833 | 376 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.016R | 6 | +0.051R | +0.067R | $-0.61 |
| UCTT-2025-05-01 | 0.833 | 347 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.016R | 6 | +0.052R | +0.068R | $-0.61 |
| UCTT-2025-05-01 | 0.833 | 347 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.016R | 6 | +0.052R | +0.068R | $-0.61 |
| UCTT-2025-05-01 | 0.833 | 347 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.016R | 6 | +0.052R | +0.068R | $-0.61 |
| UCTT-2026-03-06 | 0.772 | 43 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.036R | 6 | +0.115R | +0.151R | $-1.36 |
| UCTT-2026-03-06 | 0.772 | 43 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.036R | 6 | +0.115R | +0.151R | $-1.36 |
| UCTT-2026-03-06 | 0.772 | 43 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.036R | 6 | +0.115R | +0.151R | $-1.36 |
| UCTT-2026-03-30 | 0.833 | 13 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.078R | 6 | +0.247R | +0.325R | $-2.93 |
| UCTT-2026-03-30 | 0.833 | 13 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.078R | 6 | +0.247R | +0.325R | $-2.93 |
| UCTT-2026-03-30 | 0.833 | 13 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.078R | 6 | +0.247R | +0.325R | $-2.93 |
| WULF-2021-09-01 | 0.767 | 1697 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2021-09-01 | 0.767 | 1697 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2021-09-01 | 0.767 | 1697 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2021-09-21 | 0.833 | 1659 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2021-09-21 | 0.833 | 1659 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2021-09-21 | 0.833 | 1659 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2021-12-21 | 0.833 | 1586 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2021-12-21 | 0.833 | 1586 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2021-12-21 | 0.833 | 1586 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-03-16 | 0.767 | 1479 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-03-16 | 0.767 | 1479 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-03-16 | 0.767 | 1479 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-05-24 | 0.767 | 1429 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-05-24 | 0.767 | 1429 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-05-24 | 0.767 | 1429 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-07-12 | 0.933 | 1388 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-07-12 | 0.933 | 1388 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-07-12 | 0.933 | 1388 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-07-27 | 0.767 | 1346 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-07-27 | 0.767 | 1346 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-07-27 | 0.767 | 1346 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-09-26 | 0.833 | 1309 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-09-26 | 0.833 | 1309 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-09-26 | 0.833 | 1309 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-11-09 | 0.767 | 1270 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-11-09 | 0.767 | 1270 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2022-11-09 | 0.767 | 1270 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2023-01-19 | 0.767 | 1186 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2023-01-19 | 0.767 | 1186 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2023-01-19 | 0.767 | 1186 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2023-12-11 | 0.767 | 848 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2023-12-11 | 0.767 | 848 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2023-12-11 | 0.767 | 848 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-05-01 | 0.767 | 728 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-05-01 | 0.767 | 728 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-05-01 | 0.767 | 728 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-07-11 | 0.767 | 646 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-07-11 | 0.767 | 646 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-07-11 | 0.767 | 646 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-09-16 | 0.767 | 583 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-09-16 | 0.767 | 583 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-09-16 | 0.767 | 583 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-11-26 | 0.833 | 521 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-11-26 | 0.833 | 521 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-11-26 | 0.833 | 521 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-12-10 | 0.767 | 501 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-12-10 | 0.767 | 501 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-12-10 | 0.767 | 501 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-12-30 | 0.767 | 487 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-12-30 | 0.767 | 487 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2024-12-30 | 0.767 | 487 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2025-10-22 | 0.767 | 182 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2025-10-22 | 0.767 | 182 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2025-10-22 | 0.767 | 182 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2025-11-14 | 0.833 | 136 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2025-11-14 | 0.833 | 136 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2025-11-14 | 0.833 | 136 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2026-03-06 | 0.929 | 46 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2026-03-06 | 0.929 | 46 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| WULF-2026-03-06 | 0.929 | 46 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2021-07-07 | 0.933 | 1768 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2021-07-07 | 0.933 | 1768 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2021-07-07 | 0.933 | 1768 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2021-08-03 | 0.933 | 1735 | A_minervini_trail_ma | open | 2026-05-20 | 2026-05-22 | open_at_data_tail | -0.017R | 2 | +0.139R | +0.156R | $-0.62 |
| YOU-2021-08-03 | 0.933 | 1735 | B_fixed_R_multiple | open | 2026-05-20 | 2026-05-22 | open_at_data_tail | -0.017R | 2 | +0.139R | +0.156R | $-0.62 |
| YOU-2021-08-03 | 0.933 | 1735 | C_close_below_50d | open | 2026-05-20 | 2026-05-22 | open_at_data_tail | -0.017R | 2 | +0.139R | +0.156R | $-0.62 |
| YOU-2022-05-10 | 0.833 | 1459 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2022-05-10 | 0.833 | 1459 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2022-05-10 | 0.833 | 1459 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2022-06-30 | 0.767 | 1408 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2022-06-30 | 0.767 | 1408 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2022-06-30 | 0.767 | 1408 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2022-08-31 | 0.767 | 1334 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2022-08-31 | 0.767 | 1334 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2022-08-31 | 0.767 | 1334 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2022-10-14 | 0.767 | 1290 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2022-10-14 | 0.767 | 1290 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2022-10-14 | 0.767 | 1290 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2022-12-28 | 0.767 | 1219 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2022-12-28 | 0.767 | 1219 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2022-12-28 | 0.767 | 1219 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2023-04-06 | 0.767 | 1116 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2023-04-06 | 0.767 | 1116 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2023-04-06 | 0.767 | 1116 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2023-05-09 | 0.767 | 1078 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2023-05-09 | 0.767 | 1078 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2023-05-09 | 0.767 | 1078 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2023-07-06 | 0.833 | 1033 | A_minervini_trail_ma | open | 2026-05-20 | 2026-05-22 | open_at_data_tail | -0.006R | 2 | +0.051R | +0.057R | $-0.23 |
| YOU-2023-07-06 | 0.833 | 1033 | B_fixed_R_multiple | open | 2026-05-20 | 2026-05-22 | open_at_data_tail | -0.006R | 2 | +0.051R | +0.057R | $-0.23 |
| YOU-2023-07-06 | 0.833 | 1033 | C_close_below_50d | open | 2026-05-20 | 2026-05-22 | open_at_data_tail | -0.006R | 2 | +0.051R | +0.057R | $-0.23 |
| YOU-2024-01-03 | 0.767 | 850 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2024-01-03 | 0.767 | 850 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2024-01-03 | 0.767 | 850 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2024-01-31 | 0.767 | 816 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2024-01-31 | 0.767 | 816 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2024-01-31 | 0.767 | 816 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2024-11-18 | 0.767 | 519 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2024-11-18 | 0.767 | 519 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2024-11-18 | 0.767 | 519 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2025-05-01 | 0.767 | 364 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2025-05-01 | 0.767 | 364 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2025-05-01 | 0.767 | 364 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2025-12-08 | 0.767 | 108 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2025-12-08 | 0.767 | 108 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2025-12-08 | 0.767 | 108 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2026-02-03 | 0.776 | 70 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2026-02-03 | 0.776 | 70 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2026-02-03 | 0.776 | 70 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2026-04-29 | 0.833 | 9 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2026-04-29 | 0.833 | 9 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2026-04-29 | 0.833 | 9 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |

## Near-miss diagnostic (untriggered patterns; Ruleset A surface; max forward close as % of peak)

| pattern_id | composite | fwd_bars_in_window | max_forward_close | %_of_peak | center_peak |
|------------|-----------|--------------------|--------------------|-----------|-------------|
| TSHA-2023-04-10 | 0.767 | 1 | 6.30 | 724.1% | 0.87 |
| TSHA-2023-12-20 | 0.833 | 1 | 6.30 | 328.1% | 1.92 |
| TSHA-2024-08-05 | 0.833 | 1 | 6.30 | 272.7% | 2.31 |
| TSHA-2022-12-07 | 0.767 | 1 | 6.30 | 265.8% | 2.37 |
| TSHA-2024-06-26 | 0.767 | 1 | 6.30 | 256.1% | 2.46 |
| TSHA-2025-05-28 | 0.933 | 1 | 6.30 | 218.7% | 2.88 |
| TSHA-2024-04-04 | 0.767 | 1 | 6.30 | 195.7% | 3.22 |
| TSHA-2022-09-07 | 0.767 | 1 | 6.30 | 171.2% | 3.68 |
| TSHA-2026-03-24 | 0.767 | 1 | 6.30 | 137.6% | 4.58 |
| TSHA-2022-07-29 | 0.767 | 1 | 6.30 | 129.1% | 4.88 |
| TSHA-2026-02-05 | 0.733 | 1 | 6.30 | 128.8% | 4.89 |
| TSHA-2026-01-16 | 0.843 | 1 | 6.30 | 123.8% | 5.09 |
| DNTH-2026-02-13 | 0.765 | 3 | 87.80 | 101.0% | 86.92 |
| TSHA-2022-02-23 | 0.767 | 1 | 6.30 | 95.7% | 6.58 |
| TSHA-2022-03-28 | 0.767 | 1 | 6.30 | 93.1% | 6.77 |
| TROX-2023-05-16 | 0.767 | 8 | 10.48 | 86.3% | 12.15 |
| RNG-2022-07-14 | 0.833 | 8 | 47.75 | 81.8% | 58.34 |
| RNG-2022-06-30 | 0.767 | 9 | 47.75 | 77.9% | 61.33 |
| TROX-2023-03-15 | 0.767 | 8 | 10.48 | 72.9% | 14.38 |
| TROX-2022-11-21 | 0.767 | 8 | 10.48 | 71.1% | 14.75 |
| TROX-2024-09-10 | 0.767 | 8 | 10.48 | 71.1% | 14.75 |
| RNG-2022-05-24 | 0.767 | 9 | 47.75 | 70.2% | 67.98 |
| TROX-2022-07-14 | 0.767 | 8 | 10.48 | 62.5% | 16.77 |
| TROX-2023-02-24 | 0.767 | 8 | 10.48 | 62.4% | 16.79 |
| TROX-2022-06-23 | 0.767 | 8 | 10.48 | 61.1% | 17.16 |
| TROX-2022-04-29 | 0.933 | 8 | 10.48 | 55.7% | 18.81 |
| TROX-2022-05-12 | 0.767 | 8 | 10.48 | 52.7% | 19.88 |
| TROX-2022-01-28 | 0.767 | 8 | 10.48 | 43.8% | 23.95 |
| TROX-2021-12-20 | 0.833 | 8 | 10.48 | 40.7% | 25.78 |
| RLMD-2022-05-12 | 0.767 | 8 | 7.49 | 33.7% | 22.21 |
| RLMD-2021-12-03 | 0.933 | 8 | 7.49 | 31.6% | 23.67 |
| RLMD-2021-10-27 | 0.767 | 8 | 7.49 | 28.5% | 26.29 |
| RNG-2022-01-27 | 0.767 | 8 | 47.75 | 27.1% | 176.49 |
| RNG-2021-12-16 | 0.767 | 8 | 47.75 | 24.5% | 194.53 |
| WULF-2021-09-01 | 0.767 | 0 | n/a | n/a | 30.33 |
| WULF-2021-09-21 | 0.833 | 0 | n/a | n/a | 30.65 |
| WULF-2021-12-21 | 0.833 | 0 | n/a | n/a | 15.05 |
| WULF-2022-03-16 | 0.767 | 0 | n/a | n/a | 9.28 |
| WULF-2022-05-24 | 0.767 | 0 | n/a | n/a | 3.49 |
| WULF-2022-07-12 | 0.933 | 0 | n/a | n/a | 1.76 |
| WULF-2022-07-27 | 0.767 | 0 | n/a | n/a | 1.93 |
| WULF-2022-09-26 | 0.833 | 0 | n/a | n/a | 1.78 |
| WULF-2022-11-09 | 0.767 | 0 | n/a | n/a | 1.24 |
| WULF-2023-01-19 | 0.767 | 0 | n/a | n/a | 1.11 |
| WULF-2023-12-11 | 0.767 | 0 | n/a | n/a | 3.02 |
| WULF-2024-05-01 | 0.767 | 0 | n/a | n/a | 2.42 |
| WULF-2024-07-11 | 0.767 | 0 | n/a | n/a | 6.38 |
| WULF-2024-09-16 | 0.767 | 0 | n/a | n/a | 5.37 |
| WULF-2024-11-26 | 0.833 | 0 | n/a | n/a | 8.12 |
| WULF-2024-12-10 | 0.767 | 0 | n/a | n/a | 8.24 |
| WULF-2024-12-30 | 0.767 | 0 | n/a | n/a | 6.50 |
| WULF-2025-10-22 | 0.767 | 0 | n/a | n/a | 16.10 |
| WULF-2025-11-14 | 0.833 | 0 | n/a | n/a | 15.83 |
| WULF-2026-03-06 | 0.929 | 0 | n/a | n/a | 16.86 |
| YOU-2021-07-07 | 0.933 | 0 | n/a | n/a | 44.85 |
| YOU-2022-05-10 | 0.833 | 0 | n/a | n/a | 34.37 |
| YOU-2022-06-30 | 0.767 | 0 | n/a | n/a | 22.63 |
| YOU-2022-08-31 | 0.767 | 0 | n/a | n/a | 26.10 |
| YOU-2022-10-14 | 0.767 | 0 | n/a | n/a | 27.63 |
| YOU-2022-12-28 | 0.767 | 0 | n/a | n/a | 30.67 |
| YOU-2023-04-06 | 0.767 | 0 | n/a | n/a | 26.66 |
| YOU-2023-05-09 | 0.767 | 0 | n/a | n/a | 26.93 |
| YOU-2024-01-03 | 0.767 | 0 | n/a | n/a | 22.22 |
| YOU-2024-01-31 | 0.767 | 0 | n/a | n/a | 20.40 |
| YOU-2024-11-18 | 0.767 | 0 | n/a | n/a | 27.79 |
| YOU-2025-05-01 | 0.767 | 0 | n/a | n/a | 26.28 |
| YOU-2025-12-08 | 0.767 | 0 | n/a | n/a | 41.08 |
| YOU-2026-02-03 | 0.776 | 0 | n/a | n/a | 48.92 |
| YOU-2026-04-29 | 0.833 | 0 | n/a | n/a | 60.94 |

## Notes

- R-multiple = (exit_price - entry_price) / (entry_price - initial_stop).
- Win-rate denominator = closed trades (excludes untriggered + open).
- Entry = next-session open after first close > center_peak_price.
- Initial stop = trough_2_price * 0.99 (canonical W right-shoulder).
- Trigger search window: max(trough_1, trough_2, asof) + 1 BD lower, asof + 60 BD upper.
- All exits CLOSE-based (no intraday Low/High triggers) per dispatch brief.
- OHLCV source: V2 Shape A reader at ~/swing-data/prices-cache/ (L2 LOCK preserved).
- L6 caveat: forward-walk bars come from CURRENT archive; may differ from V1 contemporaneous state.
