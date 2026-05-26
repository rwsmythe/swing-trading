# Pattern Cohort Detector Evaluator Summary

- generated_at_utc: 2026-05-26T08:14:00.540131+00:00
- harness_version: 0.1.0
- cohort_input_mode: csv
- cohort_input_path: exports\research\cohorts\r2a_tightness_days_required_sp1.csv
- cohort_entries_count: 7
- cohort_unique_tickers_count: 7
- cohort_unique_asof_dates_count: 6
- window_mode: per-window
- template_match_mode: on
- runtime_seconds: 117.10
- l2_lock_preserved: true

## Headline: per-pattern-class summary

| pattern_class | entries_evaluated | composite>=0.5 | composite>=0.7 | composite>=0.9 | max_composite |
|---|---|---|---|---|---|
| double_bottom_w | 3391 | 1259 | 292 | 30 | 1.0000 |

## Per-pattern-class drill-down

### double_bottom_w

| cohort_entry_id | ticker | asof_date | window_index | stage_observed | geometric_score | template_match_score | composite_score |
|---|---|---|---|---|---|---|---|
| 4 | TROX | 2026-04-29 | 115 | stage_2 | 1.0000 | (none) | 1.0000 |
| 0 | NAT | 2026-05-12 | 95 | stage_2 | 0.9333 | (none) | 0.9333 |
| 0 | NAT | 2026-05-12 | 323 | stage_2 | 0.9333 | (none) | 0.9333 |
| 0 | NAT | 2026-05-12 | 370 | stage_2 | 0.9333 | (none) | 0.9333 |
| 0 | NAT | 2026-05-12 | 494 | stage_2 | 0.9333 | (none) | 0.9333 |
| 0 | NAT | 2026-05-12 | 496 | stage_2 | 0.9333 | (none) | 0.9333 |
| 1 | RLMD | 2026-05-08 | 15 | stage_2 | 0.9333 | (none) | 0.9333 |
| 1 | RLMD | 2026-05-08 | 79 | stage_2 | 0.9333 | (none) | 0.9333 |
| 2 | SEI | 2026-05-08 | 133 | stage_2 | 0.9333 | (none) | 0.9333 |
| 3 | KOD | 2026-04-30 | 77 | stage_2 | 0.9333 | (none) | 0.9333 |
| 3 | KOD | 2026-04-30 | 80 | stage_2 | 0.9333 | (none) | 0.9333 |
| 3 | KOD | 2026-04-30 | 203 | stage_2 | 0.9333 | (none) | 0.9333 |
| 4 | TROX | 2026-04-29 | 129 | stage_2 | 0.9333 | (none) | 0.9333 |
| 4 | TROX | 2026-04-29 | 212 | stage_2 | 0.9333 | (none) | 0.9333 |
| 4 | TROX | 2026-04-29 | 266 | stage_2 | 0.9333 | (none) | 0.9333 |
| 4 | TROX | 2026-04-29 | 341 | stage_2 | 0.9333 | (none) | 0.9333 |
| 5 | FRO | 2026-04-28 | 89 | stage_2 | 0.9333 | (none) | 0.9333 |
| 5 | FRO | 2026-04-28 | 170 | stage_2 | 0.9333 | (none) | 0.9333 |
| 5 | FRO | 2026-04-28 | 216 | stage_2 | 0.9333 | (none) | 0.9333 |
| 5 | FRO | 2026-04-28 | 266 | stage_2 | 0.9333 | (none) | 0.9333 |
| 5 | FRO | 2026-04-28 | 287 | stage_2 | 0.9333 | (none) | 0.9333 |
| 5 | FRO | 2026-04-28 | 486 | stage_2 | 0.9333 | (none) | 0.9333 |
| 5 | FRO | 2026-04-28 | 548 | stage_2 | 0.9333 | (none) | 0.9333 |
| 5 | FRO | 2026-04-28 | 606 | stage_2 | 0.9333 | (none) | 0.9333 |
| 6 | OII | 2026-04-21 | 99 | stage_2 | 0.9333 | (none) | 0.9333 |
| 6 | OII | 2026-04-21 | 125 | stage_2 | 0.9333 | (none) | 0.9333 |
| 6 | OII | 2026-04-21 | 293 | stage_2 | 0.9333 | (none) | 0.9333 |
| 6 | OII | 2026-04-21 | 554 | stage_2 | 0.9333 | (none) | 0.9333 |
| 6 | OII | 2026-04-21 | 613 | stage_2 | 0.9333 | (none) | 0.9333 |
| 6 | OII | 2026-04-21 | 1116 | stage_2 | 0.9333 | (none) | 0.9333 |
| 3 | KOD | 2026-04-30 | 259 | stage_2 | 0.8333 | 0.8915 | 0.8566 |
| 1 | RLMD | 2026-05-08 | 172 | stage_2 | 0.8333 | 0.8685 | 0.8474 |
| 3 | KOD | 2026-04-30 | 255 | stage_2 | 0.7667 | 0.9470 | 0.8388 |
| 4 | TROX | 2026-04-29 | 373 | stage_2 | 0.7667 | 0.9360 | 0.8344 |
| 0 | NAT | 2026-05-12 | 81 | stage_2 | 0.8333 | (none) | 0.8333 |
| 0 | NAT | 2026-05-12 | 86 | stage_2 | 0.8333 | (none) | 0.8333 |
| 0 | NAT | 2026-05-12 | 164 | stage_2 | 0.8333 | (none) | 0.8333 |
| 0 | NAT | 2026-05-12 | 257 | stage_2 | 0.8333 | (none) | 0.8333 |
| 0 | NAT | 2026-05-12 | 346 | stage_2 | 0.8333 | (none) | 0.8333 |
| 0 | NAT | 2026-05-12 | 361 | stage_2 | 0.8333 | (none) | 0.8333 |
| 0 | NAT | 2026-05-12 | 417 | stage_2 | 0.8333 | (none) | 0.8333 |
| 1 | RLMD | 2026-05-08 | 73 | stage_2 | 0.8333 | (none) | 0.8333 |
| 2 | SEI | 2026-05-08 | 63 | stage_2 | 0.8333 | (none) | 0.8333 |
| 3 | KOD | 2026-04-30 | 63 | stage_2 | 0.8333 | (none) | 0.8333 |
| 3 | KOD | 2026-04-30 | 229 | stage_2 | 0.8333 | (none) | 0.8333 |
| 3 | KOD | 2026-04-30 | 231 | stage_2 | 0.8333 | (none) | 0.8333 |
| 4 | TROX | 2026-04-29 | 96 | stage_2 | 0.8333 | (none) | 0.8333 |
| 4 | TROX | 2026-04-29 | 149 | stage_2 | 0.8333 | (none) | 0.8333 |
| 4 | TROX | 2026-04-29 | 186 | stage_2 | 0.8333 | (none) | 0.8333 |
| 4 | TROX | 2026-04-29 | 223 | stage_2 | 0.8333 | (none) | 0.8333 |

## Skip-reason summary

| skip_reason | count |
|---|---|
| archive_missing_skip | 0 |
| coverage_skip | 0 |
| detector_error_all | 0 |
| no_windows | 0 |
| window_generation_error | 0 |

## Notes

- pattern_exemplars corpus is read at harness invocation time; corpus drift between cohort-input-time and invocation-time may shift template-match Pass 2 verdicts. See method-record L1 limitation.
- OHLCV archive bar-content TEMPORAL mutation per cumulative gotcha #26 family: intervening pipeline runs may overwrite historical bars between cohort-input-time and harness-invocation-time. See method-record L2 limitation.
- current_stage lookup uses CURRENT operator DB state; if eval_runs have been pruned between cohort-input-time and harness-invocation-time, stage_observed may shift. See method-record L3 limitation.

## Manifest summary

- entries_processed: 7
- verdicts_emitted: 3391
- detectors_invoked: vcp, flat_base, cup_with_handle, high_tight_flag, double_bottom_w
- pattern_exemplars_corpus_size_at_invocation: 34
- pattern_exemplars_filtered_size: 15
- runtime_seconds: 117.10
- both_exist_diagnostic.count: 0
