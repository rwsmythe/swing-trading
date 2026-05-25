# Double-Bottom-W Walk-Forward Backtest Summary

**Cohort:** composite>=0.7 double_bottom_w; recency<=60d (max_observed_asof) (12 unique W patterns)

**Cohort source:** tests\fixtures\research\double_bottom_w_backtest\cohort.json
**Recency filter:** trough_2 within 60 calendar days of asof (12 of 172 verdicts passed).
**Both-exist diagnostic:** 1 ticker-reads hit Shape A + legacy (Shape A wins per OQ-18).

## Per-ruleset aggregate stats

| Ruleset | Patterns | Triggered | Closed | Winners | Losers | Untrig | Open | Win-rate | Avg R win | Avg R loser | Expectancy R closed | Avg days held (closed) | Avg days held (open) |
|---------|----------|-----------|--------|---------|--------|--------|------|----------|-----------|-------------|---------------------|------------------------|----------------------|
| A_minervini_trail_ma | 12 | 7 | 2 | 0 | 2 | 5 | 5 | 0.0% | n/a | -0.708R | -0.708R | 3.5d | 7.6d |
| B_fixed_R_multiple | 12 | 7 | 0 | 0 | 0 | 5 | 7 | n/a | n/a | n/a | n/a | n/a | 7.1d |
| C_close_below_50d | 12 | 7 | 2 | 0 | 2 | 5 | 5 | 0.0% | n/a | -0.708R | -0.708R | 3.5d | 7.6d |

## Exit-reason breakdown

| Ruleset | stop_hit | trail_stop | target_3R | close_below_50d | open_at_data_tail | untriggered | ohlcv_empty | entry_gap_below_stop |
|---------|----------|------------|-----------|-----------------|-------------------|-------------|-------------|----------------------|
| A_minervini_trail_ma | 0 | 0 | 0 | 2 | 5 | 5 | 0 | 0 |
| B_fixed_R_multiple | 0 | 0 | 0 | 0 | 7 | 5 | 0 | 0 |
| C_close_below_50d | 0 | 0 | 0 | 2 | 5 | 5 | 0 | 0 |

## Per-pattern detail (composite>=0.7; sorted by ticker then trough_1_date)

| pattern_id | composite | days_t2_to_asof | ruleset | status | entry_date | exit_date | exit_reason | R-multiple | days_held |
|------------|-----------|-----------------|---------|--------|------------|-----------|-------------|------------|-----------|
| DK-2026-03-09 | 0.741 | 53 | A_minervini_trail_ma | closed | 2026-05-20 | 2026-05-21 | close_below_50d | -0.960R | 1 |
| DK-2026-03-09 | 0.741 | 53 | B_fixed_R_multiple | open | 2026-05-20 | 2026-05-22 | open_at_data_tail | -0.483R | 2 |
| DK-2026-03-09 | 0.741 | 53 | C_close_below_50d | closed | 2026-05-20 | 2026-05-21 | close_below_50d | -0.960R | 1 |
| DNTH-2026-02-13 | 0.765 | 38 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a |
| DNTH-2026-02-13 | 0.765 | 38 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a |
| DNTH-2026-02-13 | 0.765 | 38 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a |
| KOD-2026-02-05 | 0.857 | 36 | A_minervini_trail_ma | open | 2026-05-01 | 2026-05-11 | open_at_data_tail | -0.156R | 10 |
| KOD-2026-02-05 | 0.857 | 36 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-11 | open_at_data_tail | -0.156R | 10 |
| KOD-2026-02-05 | 0.857 | 36 | C_close_below_50d | open | 2026-05-01 | 2026-05-11 | open_at_data_tail | -0.156R | 10 |
| OII-2026-03-13 | 0.833 | 20 | A_minervini_trail_ma | open | 2026-04-23 | 2026-04-27 | open_at_data_tail | +0.780R | 4 |
| OII-2026-03-13 | 0.833 | 20 | B_fixed_R_multiple | open | 2026-04-23 | 2026-04-27 | open_at_data_tail | +0.780R | 4 |
| OII-2026-03-13 | 0.833 | 20 | C_close_below_50d | open | 2026-04-23 | 2026-04-27 | open_at_data_tail | +0.780R | 4 |
| RNG-2026-03-27 | 0.767 | 20 | A_minervini_trail_ma | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.284R | 8 |
| RNG-2026-03-27 | 0.767 | 20 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.284R | 8 |
| RNG-2026-03-27 | 0.767 | 20 | C_close_below_50d | open | 2026-05-04 | 2026-05-12 | open_at_data_tail | -0.284R | 8 |
| TROX-2026-02-20 | 0.834 | 54 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.456R | 6 |
| TROX-2026-02-20 | 0.834 | 54 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-11 | open_at_data_tail | -0.201R | 10 |
| TROX-2026-02-20 | 0.834 | 54 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.456R | 6 |
| TSHA-2026-02-05 | 0.733 | 50 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a |
| TSHA-2026-02-05 | 0.733 | 50 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a |
| TSHA-2026-02-05 | 0.733 | 50 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a |
| TSHA-2026-03-24 | 0.767 | 47 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a |
| TSHA-2026-03-24 | 0.767 | 47 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a |
| TSHA-2026-03-24 | 0.767 | 47 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a |
| UCTT-2026-03-06 | 0.772 | 43 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.036R | 8 |
| UCTT-2026-03-06 | 0.772 | 43 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.036R | 8 |
| UCTT-2026-03-06 | 0.772 | 43 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.036R | 8 |
| UCTT-2026-03-30 | 0.833 | 13 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.078R | 8 |
| UCTT-2026-03-30 | 0.833 | 13 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.078R | 8 |
| UCTT-2026-03-30 | 0.833 | 13 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.078R | 8 |
| WULF-2026-03-06 | 0.929 | 46 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a |
| WULF-2026-03-06 | 0.929 | 46 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a |
| WULF-2026-03-06 | 0.929 | 46 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a |
| YOU-2026-04-29 | 0.833 | 9 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a |
| YOU-2026-04-29 | 0.833 | 9 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a |
| YOU-2026-04-29 | 0.833 | 9 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a |

## Near-miss diagnostic (untriggered patterns; Ruleset A surface; max forward close as % of peak)

| pattern_id | composite | fwd_bars_in_window | max_forward_close | %_of_peak | center_peak |
|------------|-----------|--------------------|--------------------|-----------|-------------|
| TSHA-2026-03-24 | 0.767 | 1 | 6.30 | 137.6% | 4.58 |
| TSHA-2026-02-05 | 0.733 | 1 | 6.30 | 128.8% | 4.89 |
| DNTH-2026-02-13 | 0.765 | 3 | 87.80 | 101.0% | 86.92 |
| WULF-2026-03-06 | 0.929 | 0 | n/a | n/a | 16.86 |
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
