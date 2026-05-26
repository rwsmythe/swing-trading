# Pattern Cohort Detector Evaluator Summary

- generated_at_utc: 2026-05-26T00:04:11.396332+00:00
- harness_version: 0.1.0
- cohort_input_mode: csv
- cohort_input_path: exports\research\cohorts\w_bottom_ruleset_comparison_sp500_apr_may_2026.csv
- cohort_entries_count: 2064
- cohort_unique_tickers_count: 516
- cohort_unique_asof_dates_count: 4
- window_mode: per-window
- template_match_mode: on
- runtime_seconds: 118.39
- l2_lock_preserved: true

## Headline: per-pattern-class summary

| pattern_class | entries_evaluated | composite>=0.5 | composite>=0.7 | composite>=0.9 | max_composite |
|---|---|---|---|---|---|
| double_bottom_w | 166007 | 608 | 186 | 19 | 1.0000 |

## Per-pattern-class drill-down

### double_bottom_w

| cohort_entry_id | ticker | asof_date | window_index | stage_observed | geometric_score | template_match_score | composite_score |
|---|---|---|---|---|---|---|---|
| 1433 | ON | 2026-04-29 | 65 | stage_2 | 1.1000 | (none) | 1.0000 |
| 942 | HPE | 2026-05-13 | 65 | stage_2 | 0.9333 | 0.9528 | 0.9411 |
| 941 | HPE | 2026-04-29 | 65 | stage_2 | 0.9333 | 0.9444 | 0.9378 |
| 941 | HPE | 2026-04-29 | 42 | stage_2 | 0.9333 | (none) | 0.9333 |
| 941 | HPE | 2026-04-29 | 48 | stage_2 | 0.9333 | (none) | 0.9333 |
| 942 | HPE | 2026-05-13 | 42 | stage_2 | 0.9333 | (none) | 0.9333 |
| 942 | HPE | 2026-05-13 | 48 | stage_2 | 0.9333 | (none) | 0.9333 |
| 943 | HPE | 2026-05-22 | 42 | stage_2 | 0.9333 | (none) | 0.9333 |
| 943 | HPE | 2026-05-22 | 65 | stage_2 | 0.9333 | (none) | 0.9333 |
| 1009 | INTC | 2026-04-29 | 104 | stage_2 | 0.9333 | (none) | 0.9333 |
| 1222 | MCHP | 2026-05-13 | 17 | stage_2 | 0.9333 | (none) | 0.9333 |
| 1223 | MCHP | 2026-05-22 | 17 | stage_2 | 0.9333 | (none) | 0.9333 |
| 1434 | ON | 2026-05-13 | 65 | stage_2 | 0.9333 | (none) | 0.9333 |
| 1435 | ON | 2026-05-22 | 65 | stage_2 | 0.9333 | (none) | 0.9333 |
| 1450 | OXY | 2026-05-13 | 11 | stage_2 | 0.9333 | (none) | 0.9333 |
| 1450 | OXY | 2026-05-13 | 68 | stage_2 | 0.9333 | (none) | 0.9333 |
| 1450 | OXY | 2026-05-13 | 93 | stage_2 | 0.9333 | (none) | 0.9333 |
| 1451 | OXY | 2026-05-22 | 93 | stage_2 | 0.9333 | (none) | 0.9333 |
| 1011 | INTC | 2026-05-22 | 104 | stage_2 | 0.9333 | 0.9012 | 0.9205 |
| 1009 | INTC | 2026-04-29 | 101 | stage_2 | 0.8333 | 0.9410 | 0.8764 |
| 1011 | INTC | 2026-05-22 | 101 | stage_2 | 0.8333 | 0.9353 | 0.8741 |
| 600 | DOW | 2026-04-21 | 68 | stage_2 | 0.7667 | 0.9533 | 0.8413 |
| 1435 | ON | 2026-05-22 | 130 | stage_2 | 0.7667 | 0.9479 | 0.8392 |
| 1434 | ON | 2026-05-13 | 130 | stage_2 | 0.7667 | 0.9454 | 0.8382 |
| 1010 | INTC | 2026-05-13 | 101 | stage_2 | 0.7667 | 0.9345 | 0.8338 |
| 1434 | ON | 2026-05-13 | 131 | stage_2 | 0.7667 | 0.9338 | 0.8335 |
| 601 | DOW | 2026-04-29 | 61 | stage_2 | 0.8333 | (none) | 0.8333 |
| 602 | DOW | 2026-05-13 | 31 | stage_2 | 0.8333 | (none) | 0.8333 |
| 941 | HPE | 2026-04-29 | 32 | stage_2 | 0.8333 | (none) | 0.8333 |
| 1008 | INTC | 2026-04-21 | 101 | stage_2 | 0.8333 | (none) | 0.8333 |
| 1008 | INTC | 2026-04-21 | 104 | stage_2 | 0.8333 | (none) | 0.8333 |
| 1222 | MCHP | 2026-05-13 | 36 | stage_2 | 0.8333 | (none) | 0.8333 |
| 1223 | MCHP | 2026-05-22 | 36 | stage_2 | 0.8333 | (none) | 0.8333 |
| 1433 | ON | 2026-04-29 | 42 | stage_2 | 0.8333 | (none) | 0.8333 |
| 1433 | ON | 2026-04-29 | 87 | stage_2 | 0.8333 | (none) | 0.8333 |
| 1434 | ON | 2026-05-13 | 42 | stage_2 | 0.8333 | (none) | 0.8333 |
| 1434 | ON | 2026-05-13 | 87 | stage_2 | 0.8333 | (none) | 0.8333 |
| 1435 | ON | 2026-05-22 | 42 | stage_2 | 0.8333 | (none) | 0.8333 |
| 1435 | ON | 2026-05-22 | 87 | stage_2 | 0.8333 | (none) | 0.8333 |
| 1450 | OXY | 2026-05-13 | 60 | stage_2 | 0.8333 | (none) | 0.8333 |
| 1451 | OXY | 2026-05-22 | 60 | stage_2 | 0.8333 | (none) | 0.8333 |
| 1451 | OXY | 2026-05-22 | 70 | stage_2 | 0.8333 | (none) | 0.8333 |
| 1435 | ON | 2026-05-22 | 131 | stage_2 | 0.7667 | 0.9289 | 0.8316 |
| 602 | DOW | 2026-05-13 | 68 | stage_2 | 0.7667 | 0.8675 | 0.8070 |
| 427 | CNC | 2026-05-22 | 11 | stage_2 | 0.7667 | (none) | 0.7667 |
| 427 | CNC | 2026-05-22 | 15 | stage_2 | 0.7667 | (none) | 0.7667 |
| 427 | CNC | 2026-05-22 | 18 | stage_2 | 0.7667 | (none) | 0.7667 |
| 427 | CNC | 2026-05-22 | 24 | stage_2 | 0.7667 | (none) | 0.7667 |
| 427 | CNC | 2026-05-22 | 47 | stage_2 | 0.7667 | (none) | 0.7667 |
| 427 | CNC | 2026-05-22 | 52 | stage_2 | 0.7667 | (none) | 0.7667 |

## Skip-reason summary

| skip_reason | count |
|---|---|
| archive_missing_skip | 0 |
| coverage_skip | 4 |
| detector_error_all | 0 |
| no_windows | 0 |
| window_generation_error | 0 |

## Notes

- pattern_exemplars corpus is read at harness invocation time; corpus drift between cohort-input-time and invocation-time may shift template-match Pass 2 verdicts. See method-record L1 limitation.
- OHLCV archive bar-content TEMPORAL mutation per cumulative gotcha #26 family: intervening pipeline runs may overwrite historical bars between cohort-input-time and harness-invocation-time. See method-record L2 limitation.
- current_stage lookup uses CURRENT operator DB state; if eval_runs have been pruned between cohort-input-time and harness-invocation-time, stage_observed may shift. See method-record L3 limitation.

## Manifest summary

- entries_processed: 2064
- verdicts_emitted: 166007
- detectors_invoked: vcp, flat_base, cup_with_handle, high_tight_flag, double_bottom_w
- pattern_exemplars_corpus_size_at_invocation: 34
- pattern_exemplars_filtered_size: 15
- runtime_seconds: 118.39
- both_exist_diagnostic.count: 0
