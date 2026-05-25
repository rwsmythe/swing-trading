# Double-Bottom-W Walk-Forward Backtest Summary

**Cohort:** composite>=0.7 double_bottom_w; recency<=60d (max_observed_asof) (12 unique W patterns)

**Cohort source:** tests\fixtures\research\double_bottom_w_backtest\cohort.json
**Recency filter:** trough_2 within 60 calendar days of asof (12 of 172 verdicts passed).
**Both-exist diagnostic:** 1 ticker-reads hit Shape A + legacy (Shape A wins per OQ-18).

## Per-ruleset aggregate stats

| Ruleset | Patterns | Triggered | Closed | Winners | Losers | Untrig | Open | Win-rate | Avg R win | Avg R loser | Expectancy R closed | Avg sessions held (closed) | Avg sessions held (open) |
|---------|----------|-----------|--------|---------|--------|--------|------|----------|-----------|-------------|---------------------|------------------------|----------------------|
| A_minervini_trail_ma | 12 | 11 | 8 | 0 | 8 | 1 | 3 | 0.0% | n/a | -0.469R | -0.469R | 5.0d | 5.0d |
| B_fixed_R_multiple | 12 | 11 | 0 | 0 | 0 | 1 | 11 | n/a | n/a | n/a | n/a | n/a | 9.5d |
| C_close_below_50d | 12 | 11 | 8 | 0 | 8 | 1 | 3 | 0.0% | n/a | -0.469R | -0.469R | 5.0d | 5.0d |

## Exit-reason breakdown

| Ruleset | stop_hit | trail_stop | target_3R | close_below_50d | open_at_data_tail | untriggered | ohlcv_empty | entry_gap_below_stop |
|---------|----------|------------|-----------|-----------------|-------------------|-------------|-------------|----------------------|
| A_minervini_trail_ma | 0 | 0 | 0 | 8 | 3 | 1 | 0 | 0 |
| B_fixed_R_multiple | 0 | 0 | 0 | 0 | 11 | 1 | 0 | 0 |
| C_close_below_50d | 0 | 0 | 0 | 8 | 3 | 1 | 0 | 0 |

## Per-pattern detail (composite>=0.7; sorted by ticker then trough_1_date)

| pattern_id | composite | days_t2_to_asof | ruleset | status | entry_date | exit_date | exit_reason | R-multiple | sessions_held | peak_R | dd_to_exit_R | pnl_$ |
|------------|-----------|-----------------|---------|--------|------------|-----------|-------------|------------|---------------|--------|--------------|-------|
| DK-2026-03-09 | 0.741 | 53 | A_minervini_trail_ma | closed | 2026-05-20 | 2026-05-21 | close_below_50d | -0.960R | 1 | +0.223R | +1.183R | $-35.98 |
| DK-2026-03-09 | 0.741 | 53 | B_fixed_R_multiple | open | 2026-05-20 | 2026-05-22 | open_at_data_tail | -0.483R | 2 | +0.223R | +0.706R | $-18.11 |
| DK-2026-03-09 | 0.741 | 53 | C_close_below_50d | closed | 2026-05-20 | 2026-05-21 | close_below_50d | -0.960R | 1 | +0.223R | +1.183R | $-35.98 |
| DNTH-2026-02-13 | 0.765 | 38 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-18 | close_below_50d | -0.378R | 11 | +0.394R | +0.772R | $-14.17 |
| DNTH-2026-02-13 | 0.765 | 38 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.107R | 15 | +0.394R | +0.501R | $-4.02 |
| DNTH-2026-02-13 | 0.765 | 38 | C_close_below_50d | closed | 2026-05-01 | 2026-05-18 | close_below_50d | -0.378R | 11 | +0.394R | +0.772R | $-14.17 |
| KOD-2026-02-05 | 0.857 | 38 | A_minervini_trail_ma | closed | 2026-05-05 | 2026-05-18 | close_below_50d | -0.372R | 9 | +0.152R | +0.524R | $-13.95 |
| KOD-2026-02-05 | 0.857 | 38 | B_fixed_R_multiple | open | 2026-05-05 | 2026-05-22 | open_at_data_tail | -0.315R | 13 | +0.152R | +0.468R | $-11.82 |
| KOD-2026-02-05 | 0.857 | 38 | C_close_below_50d | closed | 2026-05-05 | 2026-05-18 | close_below_50d | -0.372R | 9 | +0.152R | +0.524R | $-13.95 |
| OII-2026-03-13 | 0.833 | 20 | A_minervini_trail_ma | closed | 2026-04-23 | 2026-04-29 | close_below_50d | -0.112R | 4 | +1.740R | +1.853R | $-4.22 |
| OII-2026-03-13 | 0.833 | 20 | B_fixed_R_multiple | open | 2026-04-23 | 2026-05-22 | open_at_data_tail | +1.133R | 21 | +1.740R | +0.607R | $+42.50 |
| OII-2026-03-13 | 0.833 | 20 | C_close_below_50d | closed | 2026-04-23 | 2026-04-29 | close_below_50d | -0.112R | 4 | +1.740R | +1.853R | $-4.22 |
| RNG-2026-03-27 | 0.767 | 20 | A_minervini_trail_ma | closed | 2026-05-04 | 2026-05-13 | close_below_50d | -0.542R | 7 | +0.266R | +0.808R | $-20.33 |
| RNG-2026-03-27 | 0.767 | 20 | B_fixed_R_multiple | open | 2026-05-04 | 2026-05-22 | open_at_data_tail | -0.147R | 14 | +0.266R | +0.413R | $-5.51 |
| RNG-2026-03-27 | 0.767 | 20 | C_close_below_50d | closed | 2026-05-04 | 2026-05-13 | close_below_50d | -0.542R | 7 | +0.266R | +0.808R | $-20.33 |
| TROX-2026-02-20 | 0.834 | 54 | A_minervini_trail_ma | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.456R | 4 | +0.137R | +0.593R | $-17.10 |
| TROX-2026-02-20 | 0.834 | 54 | B_fixed_R_multiple | open | 2026-05-01 | 2026-05-22 | open_at_data_tail | -0.699R | 15 | +0.137R | +0.836R | $-26.22 |
| TROX-2026-02-20 | 0.834 | 54 | C_close_below_50d | closed | 2026-05-01 | 2026-05-07 | close_below_50d | -0.456R | 4 | +0.137R | +0.593R | $-17.10 |
| TSHA-2026-02-05 | 0.733 | 50 | A_minervini_trail_ma | closed | 2026-05-15 | 2026-05-19 | close_below_50d | -0.471R | 2 | +0.038R | +0.509R | $-17.65 |
| TSHA-2026-02-05 | 0.733 | 50 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.323R | 5 | +0.038R | +0.362R | $-12.13 |
| TSHA-2026-02-05 | 0.733 | 50 | C_close_below_50d | closed | 2026-05-15 | 2026-05-19 | close_below_50d | -0.471R | 2 | +0.038R | +0.509R | $-17.65 |
| TSHA-2026-03-24 | 0.767 | 47 | A_minervini_trail_ma | closed | 2026-05-15 | 2026-05-19 | close_below_50d | -0.458R | 2 | +0.037R | +0.495R | $-17.16 |
| TSHA-2026-03-24 | 0.767 | 47 | B_fixed_R_multiple | open | 2026-05-15 | 2026-05-22 | open_at_data_tail | -0.314R | 5 | +0.037R | +0.352R | $-11.79 |
| TSHA-2026-03-24 | 0.767 | 47 | C_close_below_50d | closed | 2026-05-15 | 2026-05-19 | close_below_50d | -0.458R | 2 | +0.037R | +0.495R | $-17.16 |
| UCTT-2026-03-06 | 0.772 | 43 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.036R | 6 | +0.115R | +0.151R | $-1.36 |
| UCTT-2026-03-06 | 0.772 | 43 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.036R | 6 | +0.115R | +0.151R | $-1.36 |
| UCTT-2026-03-06 | 0.772 | 43 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.036R | 6 | +0.115R | +0.151R | $-1.36 |
| UCTT-2026-03-30 | 0.833 | 13 | A_minervini_trail_ma | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.078R | 6 | +0.247R | +0.325R | $-2.93 |
| UCTT-2026-03-30 | 0.833 | 13 | B_fixed_R_multiple | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.078R | 6 | +0.247R | +0.325R | $-2.93 |
| UCTT-2026-03-30 | 0.833 | 13 | C_close_below_50d | open | 2026-05-14 | 2026-05-22 | open_at_data_tail | -0.078R | 6 | +0.247R | +0.325R | $-2.93 |
| WULF-2026-03-06 | 0.929 | 46 | A_minervini_trail_ma | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | +0.279R | 3 | +0.337R | +0.058R | $+10.47 |
| WULF-2026-03-06 | 0.929 | 46 | B_fixed_R_multiple | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | +0.279R | 3 | +0.337R | +0.058R | $+10.47 |
| WULF-2026-03-06 | 0.929 | 46 | C_close_below_50d | open | 2026-05-19 | 2026-05-22 | open_at_data_tail | +0.279R | 3 | +0.337R | +0.058R | $+10.47 |
| YOU-2026-04-29 | 0.833 | 9 | A_minervini_trail_ma | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2026-04-29 | 0.833 | 9 | B_fixed_R_multiple | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |
| YOU-2026-04-29 | 0.833 | 9 | C_close_below_50d | untriggered | n/a | n/a | untriggered | n/a | n/a | n/a | n/a | n/a |

## Near-miss diagnostic (untriggered patterns; Ruleset A surface; max forward close as % of peak)

| pattern_id | composite | fwd_bars_in_window | max_forward_close | %_of_peak | center_peak |
|------------|-----------|--------------------|--------------------|-----------|-------------|
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
