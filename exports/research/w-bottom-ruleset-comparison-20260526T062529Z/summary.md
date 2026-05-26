# W-Bottom Ruleset Comparison Backtest Summary

**Cohort:** composite>=0.5 double_bottom_w; recency<=365d (max_observed_asof) (4 unique W patterns)

**Cohort source:** tests\fixtures\research\r2d_adr_min_pct\cohort.json

**Recency filter:** trough_2 within 365 calendar days of max_observed_asof (4 of 4 verdicts passed).

**Both-exist diagnostic:** 0 ticker-reads hit Shape A + legacy (Shape A wins per OQ-18).

**Rulesets:** 6 (A_minervini_trail_ma + B_fixed_R_multiple + C_close_below_50d + D_minervini_stage2_progression + E_oneil_cup_with_handle_measured_move + F_qullamaggie_momentum_burst).

## Cross-ruleset comparison (ranked by expectancy_R_closed)

| Rank | Ruleset | Win-rate | Mean R closed | Std R closed | Mean R triggered | Max drawdown closed | Avg sessions closed |
|------|---------|----------|---------------|--------------|------------------|---------------------|---------------------|
| 1 | E_oneil_cup_with_handle_measured_move | 100.0% | +0.800R | n/a | +0.023R | +0.226R | 5.0d |
| 2 | F_qullamaggie_momentum_burst | 100.0% | +0.122R | 0.030R | +0.056R | +0.081R | 5.0d |
| 3 | A_minervini_trail_ma | n/a | n/a | n/a | -0.060R | n/a | n/a |
| 4 | B_fixed_R_multiple | n/a | n/a | n/a | -0.060R | n/a | n/a |
| 5 | C_close_below_50d | n/a | n/a | n/a | -0.060R | n/a | n/a |
| 6 | D_minervini_stage2_progression | n/a | n/a | n/a | -0.060R | n/a | n/a |

## Per-ruleset aggregate stats

| Ruleset | Patterns | Triggered | Closed | Winners | Losers | Untrig | Open | Win-rate | Avg R win | Avg R loser | Expectancy R closed | Avg sessions held (closed) | Avg sessions held (open) |
|---------|----------|-----------|--------|---------|--------|--------|------|----------|-----------|-------------|---------------------|------------------------|----------------------|
| A_minervini_trail_ma | 4 | 4 | 0 | 0 | 0 | 0 | 4 | n/a | n/a | n/a | n/a | n/a | 18.8d |
| B_fixed_R_multiple | 4 | 4 | 0 | 0 | 0 | 0 | 4 | n/a | n/a | n/a | n/a | n/a | 18.8d |
| C_close_below_50d | 4 | 4 | 0 | 0 | 0 | 0 | 4 | n/a | n/a | n/a | n/a | n/a | 18.8d |
| D_minervini_stage2_progression | 4 | 4 | 0 | 0 | 0 | 0 | 4 | n/a | n/a | n/a | n/a | n/a | 18.8d |
| E_oneil_cup_with_handle_measured_move | 4 | 4 | 1 | 1 | 0 | 0 | 3 | 100.0% | +0.800R | n/a | +0.800R | 5.0d | 18.7d |
| F_qullamaggie_momentum_burst | 4 | 4 | 3 | 3 | 0 | 0 | 1 | 100.0% | +0.122R | n/a | +0.122R | 5.0d | 18.0d |

## Exit-reason breakdown

| Ruleset | momentum_gate_fail | open_at_data_tail | target_measured_move |
|---------|--------------------|-------------------|----------------------|
| A_minervini_trail_ma | 0 | 4 | 0 |
| B_fixed_R_multiple | 0 | 4 | 0 |
| C_close_below_50d | 0 | 4 | 0 |
| D_minervini_stage2_progression | 0 | 4 | 0 |
| E_oneil_cup_with_handle_measured_move | 0 | 3 | 1 |
| F_qullamaggie_momentum_burst | 3 | 1 | 0 |

## Per-composite-score-bucket analysis

| Bucket | Ruleset | Patterns | Triggered | Closed | Winners | Expectancy R closed |
|--------|---------|----------|-----------|--------|---------|---------------------|
| composite_0.7_to_0.9 | A_minervini_trail_ma | 1 | 1 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | B_fixed_R_multiple | 1 | 1 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | C_close_below_50d | 1 | 1 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | D_minervini_stage2_progression | 1 | 1 | 0 | 0 | n/a |
| composite_0.7_to_0.9 | E_oneil_cup_with_handle_measured_move | 1 | 1 | 1 | 1 | +0.800R |
| composite_0.7_to_0.9 | F_qullamaggie_momentum_burst | 1 | 1 | 1 | 1 | +0.104R |
| composite_below_0.7 | A_minervini_trail_ma | 3 | 3 | 0 | 0 | n/a |
| composite_below_0.7 | B_fixed_R_multiple | 3 | 3 | 0 | 0 | n/a |
| composite_below_0.7 | C_close_below_50d | 3 | 3 | 0 | 0 | n/a |
| composite_below_0.7 | D_minervini_stage2_progression | 3 | 3 | 0 | 0 | n/a |
| composite_below_0.7 | E_oneil_cup_with_handle_measured_move | 3 | 3 | 0 | 0 | n/a |
| composite_below_0.7 | F_qullamaggie_momentum_burst | 3 | 3 | 2 | 2 | +0.131R |

## Per-pattern detail (first 24 rows; sorted by ticker then trough_1_date)

| pattern_id | composite | days_t2_to_asof | ruleset | status | entry_date | exit_date | exit_reason | R-multiple | sessions_held | peak_R | dd_to_exit_R | pnl_$ |
|------------|-----------|-----------------|---------|--------|------------|-----------|-------------|------------|---------------|--------|--------------|-------|
| STNG-2025-04-04 | 0.500 | 337 | A_minervini_trail_ma | open | 2026-04-28 | 2026-05-26 | open_at_data_tail | -0.027R | 19 | +0.159R | +0.186R | $-1.01 |
| STNG-2025-04-04 | 0.500 | 337 | B_fixed_R_multiple | open | 2026-04-28 | 2026-05-26 | open_at_data_tail | -0.027R | 19 | +0.159R | +0.186R | $-1.01 |
| STNG-2025-04-04 | 0.500 | 337 | C_close_below_50d | open | 2026-04-28 | 2026-05-26 | open_at_data_tail | -0.027R | 19 | +0.159R | +0.186R | $-1.01 |
| STNG-2025-04-04 | 0.500 | 337 | D_minervini_stage2_progression | open | 2026-04-28 | 2026-05-26 | open_at_data_tail | -0.027R | 19 | +0.159R | +0.186R | $-1.01 |
| STNG-2025-04-04 | 0.500 | 337 | E_oneil_cup_with_handle_measured_move | open | 2026-04-28 | 2026-05-26 | open_at_data_tail | -0.174R | 19 | +1.026R | +1.200R | $-6.53 |
| STNG-2025-04-04 | 0.500 | 337 | F_qullamaggie_momentum_burst | closed | 2026-04-28 | 2026-05-05 | momentum_gate_fail | +0.105R | 5 | +0.159R | +0.054R | $+3.94 |
| STNG-2025-05-22 | 0.767 | 298 | A_minervini_trail_ma | open | 2026-04-28 | 2026-05-26 | open_at_data_tail | -0.027R | 19 | +0.158R | +0.185R | $-1.00 |
| STNG-2025-05-22 | 0.767 | 298 | B_fixed_R_multiple | open | 2026-04-28 | 2026-05-26 | open_at_data_tail | -0.027R | 19 | +0.158R | +0.185R | $-1.00 |
| STNG-2025-05-22 | 0.767 | 298 | C_close_below_50d | open | 2026-04-28 | 2026-05-26 | open_at_data_tail | -0.027R | 19 | +0.158R | +0.185R | $-1.00 |
| STNG-2025-05-22 | 0.767 | 298 | D_minervini_stage2_progression | open | 2026-04-28 | 2026-05-26 | open_at_data_tail | -0.027R | 19 | +0.158R | +0.185R | $-1.00 |
| STNG-2025-05-22 | 0.767 | 298 | E_oneil_cup_with_handle_measured_move | closed | 2026-04-28 | 2026-05-05 | target_measured_move | +0.800R | 5 | +1.026R | +0.226R | $+30.01 |
| STNG-2025-05-22 | 0.767 | 298 | F_qullamaggie_momentum_burst | closed | 2026-04-28 | 2026-05-05 | momentum_gate_fail | +0.104R | 5 | +0.158R | +0.054R | $+3.91 |
| STNG-2025-08-11 | 0.500 | 192 | A_minervini_trail_ma | open | 2026-04-28 | 2026-05-26 | open_at_data_tail | -0.040R | 19 | +0.238R | +0.278R | $-1.51 |
| STNG-2025-08-11 | 0.500 | 192 | B_fixed_R_multiple | open | 2026-04-28 | 2026-05-26 | open_at_data_tail | -0.040R | 19 | +0.238R | +0.278R | $-1.51 |
| STNG-2025-08-11 | 0.500 | 192 | C_close_below_50d | open | 2026-04-28 | 2026-05-26 | open_at_data_tail | -0.040R | 19 | +0.238R | +0.278R | $-1.51 |
| STNG-2025-08-11 | 0.500 | 192 | D_minervini_stage2_progression | open | 2026-04-28 | 2026-05-26 | open_at_data_tail | -0.040R | 19 | +0.238R | +0.278R | $-1.51 |
| STNG-2025-08-11 | 0.500 | 192 | E_oneil_cup_with_handle_measured_move | open | 2026-04-28 | 2026-05-26 | open_at_data_tail | -0.174R | 19 | +1.026R | +1.200R | $-6.53 |
| STNG-2025-08-11 | 0.500 | 192 | F_qullamaggie_momentum_burst | closed | 2026-04-28 | 2026-05-05 | momentum_gate_fail | +0.157R | 5 | +0.238R | +0.081R | $+5.89 |
| STNG-2026-01-05 | 0.648 | 38 | A_minervini_trail_ma | open | 2026-04-29 | 2026-05-26 | open_at_data_tail | -0.144R | 18 | +0.330R | +0.474R | $-5.40 |
| STNG-2026-01-05 | 0.648 | 38 | B_fixed_R_multiple | open | 2026-04-29 | 2026-05-26 | open_at_data_tail | -0.144R | 18 | +0.330R | +0.474R | $-5.40 |
| STNG-2026-01-05 | 0.648 | 38 | C_close_below_50d | open | 2026-04-29 | 2026-05-26 | open_at_data_tail | -0.144R | 18 | +0.330R | +0.474R | $-5.40 |
| STNG-2026-01-05 | 0.648 | 38 | D_minervini_stage2_progression | open | 2026-04-29 | 2026-05-26 | open_at_data_tail | -0.144R | 18 | +0.330R | +0.474R | $-5.40 |
| STNG-2026-01-05 | 0.648 | 38 | E_oneil_cup_with_handle_measured_move | open | 2026-04-29 | 2026-05-26 | open_at_data_tail | -0.359R | 18 | +0.823R | +1.182R | $-13.46 |
| STNG-2026-01-05 | 0.648 | 38 | F_qullamaggie_momentum_burst | open | 2026-04-29 | 2026-05-26 | open_at_data_tail | -0.144R | 18 | +0.330R | +0.474R | $-5.40 |

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
