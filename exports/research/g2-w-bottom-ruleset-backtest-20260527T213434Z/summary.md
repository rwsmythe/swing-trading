# G2 W-Bottom Ruleset Backtest -- Smoke Summary

Run started UTC: 2026-05-28T07:34:25.498973+00:00
Cache dir: C:\Users\rwsmy\swing-data\prices-cache

R dollar size at $7500 floor: $75.00/R (1% risk * $7500 floor; brief Sec 11 Q4 LOCK).

## Substrate: d2_expanded

Patterns: 42 of 172 raw verdicts; filter spec: composite>=0.5 + recency<=365d + 5-BD adjacency merge (D2 Amendment 5); Brief Amendment 1: brief Sec 1.3 stated N=71 (stale snapshot); actual yields 42.
Fixture: `tests\fixtures\research\double_bottom_w_backtest\cohort.json` (SHA256 `9075ac66d70401a19f11c06b681d859d3a5fbcd16e373e282c4db991bd6cc40c`).
Substrate window days (earliest-to-latest asof): 31.

| Ruleset | N_patterns | N_triggered | N_closed | Expectancy_R | Win_rate | Avg_win_R | Avg_loss_R | Profit_factor | Trigger_conv | Median_days | Open_at_tail_n | Open_at_tail_rate | Est_$/period |
|---------|-----------:|------------:|---------:|-------------:|---------:|----------:|-----------:|--------------:|-------------:|------------:|---------------:|-------------------:|-------------:|
| A_minervini_trail_ma | 42 | 38 | 30 | -0.2737 | 0.1000 | 0.0086 | 0.3051 | 0.0031 | 0.9048 | 4.0 | 8 | 0.2105 | $-9185.31 |
| B_fixed_R_multiple | 42 | 38 | 0 | n/a | n/a | n/a | n/a | n/a | 0.9048 | n/a | 38 | 1.0000 | n/a |
| C_close_below_50d | 42 | 38 | 30 | -0.2737 | 0.1000 | 0.0086 | 0.3051 | 0.0031 | 0.9048 | 4.0 | 8 | 0.2105 | $-9185.31 |
| D_minervini_stage2_progression | 42 | 38 | 0 | n/a | n/a | n/a | n/a | n/a | 0.9048 | n/a | 38 | 1.0000 | n/a |
| E_oneil_cup_with_handle_measured_move | 42 | 38 | 29 | -0.7995 | 0.2759 | 1.2374 | 1.5755 | 0.2992 | 0.9048 | 2.0 | 9 | 0.2368 | $-26829.71 |
| F_qullamaggie_momentum_burst | 42 | 38 | 26 | -0.1457 | 0.0000 | n/a | 0.1457 | 0.0000 | 0.9048 | 5.0 | 12 | 0.3158 | $-4889.10 |
| G_bulkowski_double_bottom | 42 | 29 | 24 | -0.5599 | 0.0000 | n/a | 0.5599 | 0.0000 | 0.6905 | 0.0 | 5 | 0.1724 | $-14338.07 |
| H_oneil_double_bottom_base | 42 | 12 | 12 | -2.1432 | 0.0000 | n/a | 2.1432 | 0.0000 | 0.2857 | 0.0 | 0 | 0.0000 | $-22710.98 |
| I_edwards_magee_classical_double_bottom | 42 | 13 | 11 | -0.5639 | 0.0909 | 0.0264 | 0.6229 | 0.0042 | 0.3095 | 0.0 | 2 | 0.1538 | $-6473.62 |

## Substrate: r2a_canonical_n65

Patterns: 65 of 65 raw verdicts; filter spec: verbatim (R2-A pre-filtered).
Fixture: `tests\fixtures\research\r2a_tightness_days_required\cohort.json` (SHA256 `758675b897affb4cf779259fdfe41398a3305b9480e8e3e510a358d83c4a35e7`).
Substrate window days (earliest-to-latest asof): 21.

| Ruleset | N_patterns | N_triggered | N_closed | Expectancy_R | Win_rate | Avg_win_R | Avg_loss_R | Profit_factor | Trigger_conv | Median_days | Open_at_tail_n | Open_at_tail_rate | Est_$/period |
|---------|-----------:|------------:|---------:|-------------:|---------:|----------:|-----------:|--------------:|-------------:|------------:|---------------:|-------------------:|-------------:|
| A_minervini_trail_ma | 65 | 62 | 45 | -0.2343 | 0.0000 | n/a | 0.2343 | 0.0000 | 0.9538 | 4.0 | 17 | 0.2742 | $-18935.37 |
| B_fixed_R_multiple | 65 | 62 | 1 | -1.3156 | 0.0000 | n/a | 1.3156 | 0.0000 | 0.9538 | 4.0 | 61 | 0.9839 | $-106326.78 |
| C_close_below_50d | 65 | 62 | 45 | -0.2343 | 0.0000 | n/a | 0.2343 | 0.0000 | 0.9538 | 4.0 | 17 | 0.2742 | $-18935.37 |
| D_minervini_stage2_progression | 65 | 62 | 1 | -1.3156 | 0.0000 | n/a | 1.3156 | 0.0000 | 0.9538 | 4.0 | 61 | 0.9839 | $-106326.78 |
| E_oneil_cup_with_handle_measured_move | 65 | 62 | 40 | -1.0860 | 0.2250 | 0.5118 | 1.5498 | 0.0959 | 0.9538 | 4.0 | 22 | 0.3548 | $-87769.14 |
| F_qullamaggie_momentum_burst | 65 | 62 | 56 | -0.1542 | 0.0000 | n/a | 0.1542 | 0.0000 | 0.9538 | 5.0 | 6 | 0.0968 | $-12459.33 |
| G_bulkowski_double_bottom | 65 | 55 | 48 | -0.6044 | 0.0208 | 0.0464 | 0.6183 | 0.0016 | 0.8462 | 0.0 | 7 | 0.1273 | $-43334.85 |
| H_oneil_double_bottom_base | 65 | 25 | 23 | -3.1339 | 0.0435 | 0.2132 | 3.2860 | 0.0029 | 0.3846 | 0.0 | 2 | 0.0800 | $-102131.61 |
| I_edwards_magee_classical_double_bottom | 65 | 34 | 28 | -0.4913 | 0.1071 | 0.0568 | 0.5570 | 0.0122 | 0.5231 | 0.0 | 6 | 0.1765 | $-21774.38 |

## Cross-substrate scorecard observations

Per gotcha #33 (cohort-validity-vs-verdict-criteria), each (ruleset, substrate) cell's scorecard is its own data point. Cross-substrate comparison surfaces ruleset robustness vs cohort-specificity DESCRIPTIVELY across the 9 metrics; no single categorical verdict is emitted (banned-verdict-terms LOCK preserved).
