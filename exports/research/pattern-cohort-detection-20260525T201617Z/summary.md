# Pattern Cohort Detector Evaluator Summary

- generated_at_utc: 2026-05-25T20:16:20.329681+00:00
- harness_version: 0.1.0
- cohort_input_mode: csv
- cohort_input_path: exports\research\cohorts\tightness_1.005_flips_67.csv
- cohort_entries_count: 67
- cohort_unique_tickers_count: 15
- cohort_unique_asof_dates_count: 16
- window_mode: per-window
- template_match_mode: on
- runtime_seconds: 1350.49
- l2_lock_preserved: true

## Headline: per-pattern-class summary

| pattern_class | entries_evaluated | composite>=0.5 | composite>=0.7 | composite>=0.9 | max_composite |
|---|---|---|---|---|---|
| cup_with_handle | 8674 | 1236 | 23 | 0 | 0.8750 |
| double_bottom_w | 8674 | 2665 | 725 | 86 | 0.9333 |
| flat_base | 8674 | 1108 | 180 | 0 | 0.7143 |
| high_tight_flag | 8674 | 40 | 0 | 0 | 0.6667 |
| vcp | 8674 | 167 | 63 | 0 | 0.8799 |

## Per-pattern-class drill-down

### cup_with_handle

| cohort_entry_id | ticker | asof_date | window_index | stage_observed | geometric_score | template_match_score | composite_score |
|---|---|---|---|---|---|---|---|
| 39 | YOU | 2026-04-28 | 111 | stage_2 | 0.8750 | (none) | 0.8750 |
| 42 | YOU | 2026-04-28 | 111 | stage_2 | 0.8750 | (none) | 0.8750 |
| 45 | YOU | 2026-04-28 | 111 | stage_2 | 0.8750 | (none) | 0.8750 |
| 65 | OII | 2026-04-21 | 0 | stage_2 | 0.7750 | (none) | 0.7750 |
| 66 | OII | 2026-04-21 | 0 | stage_2 | 0.7750 | (none) | 0.7750 |
| 14 | PTEN | 2026-05-08 | 123 | stage_2 | 0.6250 | 0.9662 | 0.7615 |
| 15 | PTEN | 2026-05-08 | 123 | stage_2 | 0.6250 | 0.9662 | 0.7615 |
| 14 | PTEN | 2026-05-08 | 124 | stage_2 | 0.6250 | 0.9617 | 0.7597 |
| 15 | PTEN | 2026-05-08 | 124 | stage_2 | 0.6250 | 0.9617 | 0.7597 |
| 11 | UCTT | 2026-05-12 | 73 | stage_2 | 0.7500 | (none) | 0.7500 |
| 21 | RNG | 2026-04-30 | 77 | stage_2 | 0.7500 | (none) | 0.7500 |
| 24 | RNG | 2026-04-30 | 77 | stage_2 | 0.7500 | (none) | 0.7500 |
| 26 | RNG | 2026-04-29 | 77 | stage_2 | 0.7500 | (none) | 0.7500 |
| 29 | RNG | 2026-04-29 | 77 | stage_2 | 0.7500 | (none) | 0.7500 |
| 32 | RNG | 2026-04-29 | 77 | stage_2 | 0.7500 | (none) | 0.7500 |
| 35 | RNG | 2026-04-29 | 77 | stage_2 | 0.7500 | (none) | 0.7500 |
| 38 | RNG | 2026-04-28 | 77 | stage_2 | 0.7500 | (none) | 0.7500 |
| 41 | RNG | 2026-04-28 | 77 | stage_2 | 0.7500 | (none) | 0.7500 |
| 44 | RNG | 2026-04-28 | 77 | stage_2 | 0.7500 | (none) | 0.7500 |
| 65 | OII | 2026-04-21 | 23 | stage_2 | 0.7500 | (none) | 0.7500 |
| 66 | OII | 2026-04-21 | 23 | stage_2 | 0.7500 | (none) | 0.7500 |
| 14 | PTEN | 2026-05-08 | 125 | stage_2 | 0.6250 | 0.9368 | 0.7497 |
| 15 | PTEN | 2026-05-08 | 125 | stage_2 | 0.6250 | 0.9368 | 0.7497 |
| 17 | KOD | 2026-05-01 | 165 | stage_2 | 0.5250 | 0.9486 | 0.6944 |
| 18 | KOD | 2026-05-01 | 165 | stage_2 | 0.5250 | 0.9486 | 0.6944 |
| 19 | KOD | 2026-04-30 | 165 | stage_2 | 0.5250 | 0.9483 | 0.6943 |
| 22 | KOD | 2026-04-30 | 165 | stage_2 | 0.5250 | 0.9483 | 0.6943 |
| 19 | KOD | 2026-04-30 | 166 | stage_2 | 0.5250 | 0.9428 | 0.6921 |
| 22 | KOD | 2026-04-30 | 166 | stage_2 | 0.5250 | 0.9428 | 0.6921 |
| 17 | KOD | 2026-05-01 | 166 | stage_2 | 0.5250 | 0.9428 | 0.6921 |
| 18 | KOD | 2026-05-01 | 166 | stage_2 | 0.5250 | 0.9428 | 0.6921 |
| 8 | TSHA | 2026-05-13 | 162 | stage_2 | 0.5250 | 0.9426 | 0.6920 |
| 25 | KOD | 2026-04-29 | 165 | stage_2 | 0.5250 | 0.9376 | 0.6900 |
| 28 | KOD | 2026-04-29 | 165 | stage_2 | 0.5250 | 0.9376 | 0.6900 |
| 31 | KOD | 2026-04-29 | 165 | stage_2 | 0.5250 | 0.9376 | 0.6900 |
| 34 | KOD | 2026-04-29 | 165 | stage_2 | 0.5250 | 0.9376 | 0.6900 |
| 8 | TSHA | 2026-05-13 | 161 | stage_2 | 0.5250 | 0.9368 | 0.6897 |
| 17 | KOD | 2026-05-01 | 168 | stage_2 | 0.5250 | 0.9322 | 0.6879 |
| 18 | KOD | 2026-05-01 | 168 | stage_2 | 0.5250 | 0.9322 | 0.6879 |
| 19 | KOD | 2026-04-30 | 168 | stage_2 | 0.5250 | 0.9317 | 0.6877 |
| 22 | KOD | 2026-04-30 | 168 | stage_2 | 0.5250 | 0.9317 | 0.6877 |
| 17 | KOD | 2026-05-01 | 167 | stage_2 | 0.5250 | 0.9284 | 0.6863 |
| 18 | KOD | 2026-05-01 | 167 | stage_2 | 0.5250 | 0.9284 | 0.6863 |
| 19 | KOD | 2026-04-30 | 167 | stage_2 | 0.5250 | 0.9280 | 0.6862 |
| 22 | KOD | 2026-04-30 | 167 | stage_2 | 0.5250 | 0.9280 | 0.6862 |
| 25 | KOD | 2026-04-29 | 167 | stage_2 | 0.5250 | 0.9278 | 0.6861 |
| 28 | KOD | 2026-04-29 | 167 | stage_2 | 0.5250 | 0.9278 | 0.6861 |
| 31 | KOD | 2026-04-29 | 167 | stage_2 | 0.5250 | 0.9278 | 0.6861 |
| 34 | KOD | 2026-04-29 | 167 | stage_2 | 0.5250 | 0.9278 | 0.6861 |
| 25 | KOD | 2026-04-29 | 166 | stage_2 | 0.5250 | 0.9244 | 0.6848 |

### double_bottom_w

| cohort_entry_id | ticker | asof_date | window_index | stage_observed | geometric_score | template_match_score | composite_score |
|---|---|---|---|---|---|---|---|
| 0 | YOU | 2026-05-22 | 0 | stage_2 | 0.9333 | (none) | 0.9333 |
| 1 | YOU | 2026-05-18 | 0 | stage_2 | 0.9333 | (none) | 0.9333 |
| 1 | YOU | 2026-05-18 | 3 | stage_2 | 0.9333 | (none) | 0.9333 |
| 2 | YOU | 2026-05-18 | 0 | stage_2 | 0.9333 | (none) | 0.9333 |
| 2 | YOU | 2026-05-18 | 3 | stage_2 | 0.9333 | (none) | 0.9333 |
| 3 | YOU | 2026-05-18 | 0 | stage_2 | 0.9333 | (none) | 0.9333 |
| 3 | YOU | 2026-05-18 | 3 | stage_2 | 0.9333 | (none) | 0.9333 |
| 4 | DK | 2026-05-15 | 76 | stage_2 | 0.9333 | (none) | 0.9333 |
| 4 | DK | 2026-05-15 | 79 | stage_2 | 0.9333 | (none) | 0.9333 |
| 5 | DK | 2026-05-15 | 76 | stage_2 | 0.9333 | (none) | 0.9333 |
| 5 | DK | 2026-05-15 | 79 | stage_2 | 0.9333 | (none) | 0.9333 |
| 7 | WULF | 2026-05-15 | 41 | stage_2 | 0.9333 | (none) | 0.9333 |
| 8 | TSHA | 2026-05-13 | 142 | stage_2 | 0.9333 | (none) | 0.9333 |
| 9 | NAT | 2026-05-12 | 50 | stage_2 | 0.9333 | (none) | 0.9333 |
| 9 | NAT | 2026-05-12 | 52 | stage_2 | 0.9333 | (none) | 0.9333 |
| 10 | RLMD | 2026-05-12 | 15 | stage_2 | 0.9333 | (none) | 0.9333 |
| 10 | RLMD | 2026-05-12 | 79 | stage_2 | 0.9333 | (none) | 0.9333 |
| 11 | UCTT | 2026-05-12 | 54 | stage_2 | 0.9333 | (none) | 0.9333 |
| 12 | RLMD | 2026-05-11 | 15 | stage_2 | 0.9333 | (none) | 0.9333 |
| 12 | RLMD | 2026-05-11 | 79 | stage_2 | 0.9333 | (none) | 0.9333 |
| 13 | RLMD | 2026-05-11 | 15 | stage_2 | 0.9333 | (none) | 0.9333 |
| 13 | RLMD | 2026-05-11 | 79 | stage_2 | 0.9333 | (none) | 0.9333 |
| 14 | PTEN | 2026-05-08 | 113 | stage_2 | 0.9333 | (none) | 0.9333 |
| 15 | PTEN | 2026-05-08 | 113 | stage_2 | 0.9333 | (none) | 0.9333 |
| 16 | RLMD | 2026-05-04 | 15 | stage_2 | 0.9333 | (none) | 0.9333 |
| 16 | RLMD | 2026-05-04 | 79 | stage_2 | 0.9333 | (none) | 0.9333 |
| 17 | KOD | 2026-05-01 | 116 | stage_2 | 0.9333 | (none) | 0.9333 |
| 18 | KOD | 2026-05-01 | 116 | stage_2 | 0.9333 | (none) | 0.9333 |
| 19 | KOD | 2026-04-30 | 116 | stage_2 | 0.9333 | (none) | 0.9333 |
| 20 | RLMD | 2026-04-30 | 15 | stage_2 | 0.9333 | (none) | 0.9333 |
| 20 | RLMD | 2026-04-30 | 79 | stage_2 | 0.9333 | (none) | 0.9333 |
| 21 | RNG | 2026-04-30 | 124 | stage_2 | 0.9333 | (none) | 0.9333 |
| 22 | KOD | 2026-04-30 | 116 | stage_2 | 0.9333 | (none) | 0.9333 |
| 23 | RLMD | 2026-04-30 | 15 | stage_2 | 0.9333 | (none) | 0.9333 |
| 23 | RLMD | 2026-04-30 | 79 | stage_2 | 0.9333 | (none) | 0.9333 |
| 24 | RNG | 2026-04-30 | 124 | stage_2 | 0.9333 | (none) | 0.9333 |
| 25 | KOD | 2026-04-29 | 116 | stage_2 | 0.9333 | (none) | 0.9333 |
| 26 | RNG | 2026-04-29 | 124 | stage_2 | 0.9333 | (none) | 0.9333 |
| 27 | TROX | 2026-04-29 | 23 | stage_2 | 0.9333 | (none) | 0.9333 |
| 27 | TROX | 2026-04-29 | 98 | stage_2 | 0.9333 | (none) | 0.9333 |
| 28 | KOD | 2026-04-29 | 116 | stage_2 | 0.9333 | (none) | 0.9333 |
| 29 | RNG | 2026-04-29 | 124 | stage_2 | 0.9333 | (none) | 0.9333 |
| 30 | TROX | 2026-04-29 | 23 | stage_2 | 0.9333 | (none) | 0.9333 |
| 30 | TROX | 2026-04-29 | 98 | stage_2 | 0.9333 | (none) | 0.9333 |
| 31 | KOD | 2026-04-29 | 116 | stage_2 | 0.9333 | (none) | 0.9333 |
| 32 | RNG | 2026-04-29 | 124 | stage_2 | 0.9333 | (none) | 0.9333 |
| 33 | TROX | 2026-04-29 | 23 | stage_2 | 0.9333 | (none) | 0.9333 |
| 33 | TROX | 2026-04-29 | 98 | stage_2 | 0.9333 | (none) | 0.9333 |
| 34 | KOD | 2026-04-29 | 116 | stage_2 | 0.9333 | (none) | 0.9333 |
| 35 | RNG | 2026-04-29 | 124 | stage_2 | 0.9333 | (none) | 0.9333 |

### flat_base

| cohort_entry_id | ticker | asof_date | window_index | stage_observed | geometric_score | template_match_score | composite_score |
|---|---|---|---|---|---|---|---|
| 10 | RLMD | 2026-05-12 | 24 | stage_2 | 0.7143 | (none) | 0.7143 |
| 10 | RLMD | 2026-05-12 | 25 | stage_2 | 0.7143 | (none) | 0.7143 |
| 10 | RLMD | 2026-05-12 | 26 | stage_2 | 0.7143 | (none) | 0.7143 |
| 10 | RLMD | 2026-05-12 | 27 | stage_2 | 0.7143 | (none) | 0.7143 |
| 10 | RLMD | 2026-05-12 | 28 | stage_2 | 0.7143 | (none) | 0.7143 |
| 10 | RLMD | 2026-05-12 | 37 | stage_2 | 0.7143 | (none) | 0.7143 |
| 10 | RLMD | 2026-05-12 | 38 | stage_2 | 0.7143 | (none) | 0.7143 |
| 10 | RLMD | 2026-05-12 | 39 | stage_2 | 0.7143 | (none) | 0.7143 |
| 10 | RLMD | 2026-05-12 | 40 | stage_2 | 0.7143 | (none) | 0.7143 |
| 10 | RLMD | 2026-05-12 | 41 | stage_2 | 0.7143 | (none) | 0.7143 |
| 10 | RLMD | 2026-05-12 | 42 | stage_2 | 0.7143 | (none) | 0.7143 |
| 10 | RLMD | 2026-05-12 | 43 | stage_2 | 0.7143 | (none) | 0.7143 |
| 12 | RLMD | 2026-05-11 | 24 | stage_2 | 0.7143 | (none) | 0.7143 |
| 12 | RLMD | 2026-05-11 | 25 | stage_2 | 0.7143 | (none) | 0.7143 |
| 12 | RLMD | 2026-05-11 | 26 | stage_2 | 0.7143 | (none) | 0.7143 |
| 12 | RLMD | 2026-05-11 | 27 | stage_2 | 0.7143 | (none) | 0.7143 |
| 12 | RLMD | 2026-05-11 | 28 | stage_2 | 0.7143 | (none) | 0.7143 |
| 12 | RLMD | 2026-05-11 | 37 | stage_2 | 0.7143 | (none) | 0.7143 |
| 12 | RLMD | 2026-05-11 | 38 | stage_2 | 0.7143 | (none) | 0.7143 |
| 12 | RLMD | 2026-05-11 | 39 | stage_2 | 0.7143 | (none) | 0.7143 |
| 12 | RLMD | 2026-05-11 | 40 | stage_2 | 0.7143 | (none) | 0.7143 |
| 12 | RLMD | 2026-05-11 | 41 | stage_2 | 0.7143 | (none) | 0.7143 |
| 12 | RLMD | 2026-05-11 | 42 | stage_2 | 0.7143 | (none) | 0.7143 |
| 12 | RLMD | 2026-05-11 | 43 | stage_2 | 0.7143 | (none) | 0.7143 |
| 13 | RLMD | 2026-05-11 | 24 | stage_2 | 0.7143 | (none) | 0.7143 |
| 13 | RLMD | 2026-05-11 | 25 | stage_2 | 0.7143 | (none) | 0.7143 |
| 13 | RLMD | 2026-05-11 | 26 | stage_2 | 0.7143 | (none) | 0.7143 |
| 13 | RLMD | 2026-05-11 | 27 | stage_2 | 0.7143 | (none) | 0.7143 |
| 13 | RLMD | 2026-05-11 | 28 | stage_2 | 0.7143 | (none) | 0.7143 |
| 13 | RLMD | 2026-05-11 | 37 | stage_2 | 0.7143 | (none) | 0.7143 |
| 13 | RLMD | 2026-05-11 | 38 | stage_2 | 0.7143 | (none) | 0.7143 |
| 13 | RLMD | 2026-05-11 | 39 | stage_2 | 0.7143 | (none) | 0.7143 |
| 13 | RLMD | 2026-05-11 | 40 | stage_2 | 0.7143 | (none) | 0.7143 |
| 13 | RLMD | 2026-05-11 | 41 | stage_2 | 0.7143 | (none) | 0.7143 |
| 13 | RLMD | 2026-05-11 | 42 | stage_2 | 0.7143 | (none) | 0.7143 |
| 13 | RLMD | 2026-05-11 | 43 | stage_2 | 0.7143 | (none) | 0.7143 |
| 16 | RLMD | 2026-05-04 | 24 | stage_2 | 0.7143 | (none) | 0.7143 |
| 16 | RLMD | 2026-05-04 | 25 | stage_2 | 0.7143 | (none) | 0.7143 |
| 16 | RLMD | 2026-05-04 | 26 | stage_2 | 0.7143 | (none) | 0.7143 |
| 16 | RLMD | 2026-05-04 | 27 | stage_2 | 0.7143 | (none) | 0.7143 |
| 16 | RLMD | 2026-05-04 | 28 | stage_2 | 0.7143 | (none) | 0.7143 |
| 16 | RLMD | 2026-05-04 | 37 | stage_2 | 0.7143 | (none) | 0.7143 |
| 16 | RLMD | 2026-05-04 | 38 | stage_2 | 0.7143 | (none) | 0.7143 |
| 16 | RLMD | 2026-05-04 | 39 | stage_2 | 0.7143 | (none) | 0.7143 |
| 16 | RLMD | 2026-05-04 | 40 | stage_2 | 0.7143 | (none) | 0.7143 |
| 16 | RLMD | 2026-05-04 | 41 | stage_2 | 0.7143 | (none) | 0.7143 |
| 16 | RLMD | 2026-05-04 | 42 | stage_2 | 0.7143 | (none) | 0.7143 |
| 16 | RLMD | 2026-05-04 | 43 | stage_2 | 0.7143 | (none) | 0.7143 |
| 17 | KOD | 2026-05-01 | 13 | stage_2 | 0.7143 | (none) | 0.7143 |
| 17 | KOD | 2026-05-01 | 14 | stage_2 | 0.7143 | (none) | 0.7143 |

### high_tight_flag

| cohort_entry_id | ticker | asof_date | window_index | stage_observed | geometric_score | template_match_score | composite_score |
|---|---|---|---|---|---|---|---|
| 20 | RLMD | 2026-04-30 | 182 | stage_2 | 0.6667 | (none) | 0.6667 |
| 23 | RLMD | 2026-04-30 | 182 | stage_2 | 0.6667 | (none) | 0.6667 |
| 47 | FRO | 2026-04-27 | 118 | stage_2 | 0.6667 | (none) | 0.6667 |
| 49 | FRO | 2026-04-27 | 118 | stage_2 | 0.6667 | (none) | 0.6667 |
| 51 | FRO | 2026-04-27 | 118 | stage_2 | 0.6667 | (none) | 0.6667 |
| 0 | YOU | 2026-05-22 | 125 | stage_2 | 0.5000 | (none) | 0.5000 |
| 7 | WULF | 2026-05-15 | 212 | stage_2 | 0.5000 | (none) | 0.5000 |
| 9 | NAT | 2026-05-12 | 113 | stage_2 | 0.5000 | (none) | 0.5000 |
| 10 | RLMD | 2026-05-12 | 183 | stage_2 | 0.5000 | (none) | 0.5000 |
| 12 | RLMD | 2026-05-11 | 183 | stage_2 | 0.5000 | (none) | 0.5000 |
| 13 | RLMD | 2026-05-11 | 183 | stage_2 | 0.5000 | (none) | 0.5000 |
| 16 | RLMD | 2026-05-04 | 181 | stage_2 | 0.5000 | (none) | 0.5000 |
| 16 | RLMD | 2026-05-04 | 182 | stage_2 | 0.5000 | (none) | 0.5000 |
| 20 | RLMD | 2026-04-30 | 181 | stage_2 | 0.5000 | (none) | 0.5000 |
| 21 | RNG | 2026-04-30 | 137 | stage_2 | 0.5000 | (none) | 0.5000 |
| 23 | RLMD | 2026-04-30 | 181 | stage_2 | 0.5000 | (none) | 0.5000 |
| 24 | RNG | 2026-04-30 | 137 | stage_2 | 0.5000 | (none) | 0.5000 |
| 26 | RNG | 2026-04-29 | 137 | stage_2 | 0.5000 | (none) | 0.5000 |
| 29 | RNG | 2026-04-29 | 137 | stage_2 | 0.5000 | (none) | 0.5000 |
| 32 | RNG | 2026-04-29 | 137 | stage_2 | 0.5000 | (none) | 0.5000 |
| 35 | RNG | 2026-04-29 | 137 | stage_2 | 0.5000 | (none) | 0.5000 |
| 37 | FRO | 2026-04-28 | 115 | stage_2 | 0.5000 | (none) | 0.5000 |
| 37 | FRO | 2026-04-28 | 116 | stage_2 | 0.5000 | (none) | 0.5000 |
| 37 | FRO | 2026-04-28 | 118 | stage_2 | 0.5000 | (none) | 0.5000 |
| 38 | RNG | 2026-04-28 | 137 | stage_2 | 0.5000 | (none) | 0.5000 |
| 40 | FRO | 2026-04-28 | 115 | stage_2 | 0.5000 | (none) | 0.5000 |
| 40 | FRO | 2026-04-28 | 116 | stage_2 | 0.5000 | (none) | 0.5000 |
| 40 | FRO | 2026-04-28 | 118 | stage_2 | 0.5000 | (none) | 0.5000 |
| 41 | RNG | 2026-04-28 | 137 | stage_2 | 0.5000 | (none) | 0.5000 |
| 43 | FRO | 2026-04-28 | 115 | stage_2 | 0.5000 | (none) | 0.5000 |
| 43 | FRO | 2026-04-28 | 116 | stage_2 | 0.5000 | (none) | 0.5000 |
| 43 | FRO | 2026-04-28 | 118 | stage_2 | 0.5000 | (none) | 0.5000 |
| 44 | RNG | 2026-04-28 | 137 | stage_2 | 0.5000 | (none) | 0.5000 |
| 47 | FRO | 2026-04-27 | 115 | stage_2 | 0.5000 | (none) | 0.5000 |
| 49 | FRO | 2026-04-27 | 115 | stage_2 | 0.5000 | (none) | 0.5000 |
| 51 | FRO | 2026-04-27 | 115 | stage_2 | 0.5000 | (none) | 0.5000 |
| 53 | RLMD | 2026-04-24 | 181 | stage_2 | 0.5000 | (none) | 0.5000 |
| 55 | RLMD | 2026-04-24 | 181 | stage_2 | 0.5000 | (none) | 0.5000 |
| 57 | RLMD | 2026-04-24 | 181 | stage_2 | 0.5000 | (none) | 0.5000 |
| 59 | RLMD | 2026-04-24 | 181 | stage_2 | 0.5000 | (none) | 0.5000 |
| 1 | YOU | 2026-05-18 | 125 | stage_2 | 0.3333 | (none) | 0.3333 |
| 2 | YOU | 2026-05-18 | 125 | stage_2 | 0.3333 | (none) | 0.3333 |
| 3 | YOU | 2026-05-18 | 125 | stage_2 | 0.3333 | (none) | 0.3333 |
| 4 | DK | 2026-05-15 | 117 | stage_2 | 0.3333 | (none) | 0.3333 |
| 5 | DK | 2026-05-15 | 117 | stage_2 | 0.3333 | (none) | 0.3333 |
| 11 | UCTT | 2026-05-12 | 139 | stage_2 | 0.3333 | (none) | 0.3333 |
| 11 | UCTT | 2026-05-12 | 140 | stage_2 | 0.3333 | (none) | 0.3333 |
| 37 | FRO | 2026-04-28 | 117 | stage_2 | 0.3333 | (none) | 0.3333 |
| 40 | FRO | 2026-04-28 | 117 | stage_2 | 0.3333 | (none) | 0.3333 |
| 43 | FRO | 2026-04-28 | 117 | stage_2 | 0.3333 | (none) | 0.3333 |

### vcp

| cohort_entry_id | ticker | asof_date | window_index | stage_observed | geometric_score | template_match_score | composite_score |
|---|---|---|---|---|---|---|---|
| 65 | OII | 2026-04-21 | 23 | stage_2 | 0.8571 | 0.9140 | 0.8799 |
| 66 | OII | 2026-04-21 | 23 | stage_2 | 0.8571 | 0.9140 | 0.8799 |
| 38 | RNG | 2026-04-28 | 132 | stage_2 | 0.8571 | 0.8991 | 0.8739 |
| 41 | RNG | 2026-04-28 | 132 | stage_2 | 0.8571 | 0.8991 | 0.8739 |
| 44 | RNG | 2026-04-28 | 132 | stage_2 | 0.8571 | 0.8991 | 0.8739 |
| 26 | RNG | 2026-04-29 | 132 | stage_2 | 0.8571 | 0.8975 | 0.8733 |
| 29 | RNG | 2026-04-29 | 132 | stage_2 | 0.8571 | 0.8975 | 0.8733 |
| 32 | RNG | 2026-04-29 | 132 | stage_2 | 0.8571 | 0.8975 | 0.8733 |
| 35 | RNG | 2026-04-29 | 132 | stage_2 | 0.8571 | 0.8975 | 0.8733 |
| 21 | RNG | 2026-04-30 | 132 | stage_2 | 0.8571 | 0.8959 | 0.8726 |
| 24 | RNG | 2026-04-30 | 132 | stage_2 | 0.8571 | 0.8959 | 0.8726 |
| 11 | UCTT | 2026-05-12 | 137 | stage_2 | 0.8571 | 0.8644 | 0.8600 |
| 11 | UCTT | 2026-05-12 | 134 | stage_2 | 0.8571 | (none) | 0.8571 |
| 27 | TROX | 2026-04-29 | 133 | stage_2 | 0.8571 | 0.8551 | 0.8563 |
| 30 | TROX | 2026-04-29 | 133 | stage_2 | 0.8571 | 0.8551 | 0.8563 |
| 33 | TROX | 2026-04-29 | 133 | stage_2 | 0.8571 | 0.8551 | 0.8563 |
| 36 | TROX | 2026-04-29 | 133 | stage_2 | 0.8571 | 0.8551 | 0.8563 |
| 65 | OII | 2026-04-21 | 24 | stage_2 | 0.8571 | 0.8483 | 0.8536 |
| 66 | OII | 2026-04-21 | 24 | stage_2 | 0.8571 | 0.8483 | 0.8536 |
| 27 | TROX | 2026-04-29 | 134 | stage_2 | 0.8571 | 0.8054 | 0.8364 |
| 30 | TROX | 2026-04-29 | 134 | stage_2 | 0.8571 | 0.8054 | 0.8364 |
| 33 | TROX | 2026-04-29 | 134 | stage_2 | 0.8571 | 0.8054 | 0.8364 |
| 36 | TROX | 2026-04-29 | 134 | stage_2 | 0.8571 | 0.8054 | 0.8364 |
| 11 | UCTT | 2026-05-12 | 135 | stage_2 | 0.8571 | 0.7930 | 0.8315 |
| 11 | UCTT | 2026-05-12 | 136 | stage_2 | 0.8571 | 0.7710 | 0.8227 |
| 27 | TROX | 2026-04-29 | 131 | stage_2 | 0.8571 | 0.7582 | 0.8175 |
| 30 | TROX | 2026-04-29 | 131 | stage_2 | 0.8571 | 0.7582 | 0.8175 |
| 33 | TROX | 2026-04-29 | 131 | stage_2 | 0.8571 | 0.7582 | 0.8175 |
| 36 | TROX | 2026-04-29 | 131 | stage_2 | 0.8571 | 0.7582 | 0.8175 |
| 27 | TROX | 2026-04-29 | 132 | stage_2 | 0.8571 | 0.7455 | 0.8125 |
| 30 | TROX | 2026-04-29 | 132 | stage_2 | 0.8571 | 0.7455 | 0.8125 |
| 33 | TROX | 2026-04-29 | 132 | stage_2 | 0.8571 | 0.7455 | 0.8125 |
| 36 | TROX | 2026-04-29 | 132 | stage_2 | 0.8571 | 0.7455 | 0.8125 |
| 4 | DK | 2026-05-15 | 113 | stage_2 | 0.7143 | 0.9213 | 0.7971 |
| 5 | DK | 2026-05-15 | 113 | stage_2 | 0.7143 | 0.9213 | 0.7971 |
| 4 | DK | 2026-05-15 | 114 | stage_2 | 0.7143 | 0.9101 | 0.7926 |
| 5 | DK | 2026-05-15 | 114 | stage_2 | 0.7143 | 0.9101 | 0.7926 |
| 0 | YOU | 2026-05-22 | 123 | stage_2 | 0.7143 | 0.8608 | 0.7729 |
| 16 | RLMD | 2026-05-04 | 178 | stage_2 | 0.7143 | 0.8385 | 0.7640 |
| 0 | YOU | 2026-05-22 | 122 | stage_2 | 0.7143 | 0.7998 | 0.7485 |
| 4 | DK | 2026-05-15 | 115 | stage_2 | 0.7143 | (none) | 0.7143 |
| 5 | DK | 2026-05-15 | 115 | stage_2 | 0.7143 | (none) | 0.7143 |
| 9 | NAT | 2026-05-12 | 112 | stage_2 | 0.7143 | (none) | 0.7143 |
| 11 | UCTT | 2026-05-12 | 133 | stage_2 | 0.7143 | (none) | 0.7143 |
| 16 | RLMD | 2026-05-04 | 179 | stage_2 | 0.7143 | (none) | 0.7143 |
| 16 | RLMD | 2026-05-04 | 180 | stage_2 | 0.7143 | (none) | 0.7143 |
| 21 | RNG | 2026-04-30 | 135 | stage_2 | 0.7143 | (none) | 0.7143 |
| 24 | RNG | 2026-04-30 | 135 | stage_2 | 0.7143 | (none) | 0.7143 |
| 26 | RNG | 2026-04-29 | 135 | stage_2 | 0.7143 | (none) | 0.7143 |
| 29 | RNG | 2026-04-29 | 135 | stage_2 | 0.7143 | (none) | 0.7143 |

## Skip-reason summary

| skip_reason | count |
|---|---|
| archive_missing_skip | 0 |
| coverage_skip | 0 |
| detector_error_all | 0 |
| no_windows | 0 |
| window_generation_error | 0 |

## Both-exist diagnostic (Shape A wins per OQ-18 V2 LOCK)

- count: 2
- affected_tickers (capped at 50):
  - DK
  - DK

## Notes

- pattern_exemplars corpus is read at harness invocation time; corpus drift between cohort-input-time and invocation-time may shift template-match Pass 2 verdicts. See method-record L1 limitation.
- OHLCV archive bar-content TEMPORAL mutation per cumulative gotcha #26 family: intervening pipeline runs may overwrite historical bars between cohort-input-time and harness-invocation-time. See method-record L2 limitation.
- current_stage lookup uses CURRENT operator DB state; if eval_runs have been pruned between cohort-input-time and harness-invocation-time, stage_observed may shift. See method-record L3 limitation.

## Manifest summary

- entries_processed: 67
- verdicts_emitted: 43370
- detectors_invoked: vcp, flat_base, cup_with_handle, high_tight_flag, double_bottom_w
- pattern_exemplars_corpus_size_at_invocation: 34
- pattern_exemplars_filtered_size: 15
- runtime_seconds: 1350.49
- both_exist_diagnostic.count: 2
