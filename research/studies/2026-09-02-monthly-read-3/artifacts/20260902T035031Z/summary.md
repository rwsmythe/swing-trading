# Shadow-expectancy engine - summary

Mechanical-ruleset SHADOW evidence (NOT live hand-traded counts; spec 1).

## OHLC epsilon-clamp (reader-side; log untouched; brief 2b)
  clamped_bar_count=221 clamped_bar_events=838 (<= 1.0% shape tolerance)
    ADEA 2026-07-13 clamp=0.9754%
    AMBP 2026-08-20 clamp=0.1905%
    AMBP 2026-08-26 clamp=0.3824%
    AMN 2026-07-13 clamp=0.0294%
    AMN 2026-07-16 clamp=0.1900%
    AMN 2026-08-19 clamp=0.4530%
    APLE 2026-07-16 clamp=0.1928%
    ARKG 2026-08-07 clamp=0.2091%
    ARKG 2026-08-20 clamp=0.1364%
    ARMK 2026-08-19 clamp=0.1589%
    ARMK 2026-08-31 clamp=0.1421%
    ASH 2026-08-06 clamp=0.7935%
    ASH 2026-08-18 clamp=0.0272%
    ASH 2026-08-20 clamp=0.0137%
    ATEN 2026-08-07 clamp=0.2347%
    BAX 2026-08-17 clamp=0.1158%
    BCS 2026-08-19 clamp=0.0037%
    BCS 2026-08-26 clamp=0.0369%
    BFLY 2026-08-24 clamp=0.7821%
    BFLY 2026-08-31 clamp=0.2535%

## Denominator funnel (detection-level)
total_detections=5940 collapsed_duplicate=4752 unique_signals=1188

## Unattributed signals (pre-/non-attribution; spec 7.1)
  no_candidate_join=0
  matched_no_hypothesis=0
  multi_match=0
  inconsistent_detection_series=0
  total_unattributed=0

## A+ baseline
HEADLINE realistic closed-only mean R=-0.593 (n=6)
  closed_only: realistic=-0.593 favorable=-0.593 (n=6)
  mtm_at_horizon: realistic=-0.588 favorable=-0.588 (n=7)
  forced_exit_at_horizon_open: realistic=-0.588 favorable=-0.588 (n=7)
  stop_level_adverse: realistic=-0.651 favorable=-0.651 (n=7)
win rate (closed-only) 1/6
trigger rate 7/11; per-signal expectancy [realistic]=-0.374
entry_bar_weak_close (intraday-touch entries) = 4

## Broad-watch baseline
HEADLINE realistic closed-only mean R=-0.397 (n=588)
  closed_only: realistic=-0.397 favorable=-0.297 (n=588)
  mtm_at_horizon: realistic=-0.267 favorable=-0.178 (n=662)
  forced_exit_at_horizon_open: realistic=-0.267 favorable=-0.178 (n=662)
  stop_level_adverse: realistic=-0.357 favorable=-0.268 (n=662)
win rate (closed-only) 128/588
trigger rate 662/1045; per-signal expectancy [realistic]=-0.169
entry_bar_weak_close (intraday-touch entries) = 384

## Near-A+ defensible: extension test
HEADLINE realistic closed-only mean R=-0.531 (n=10)
  closed_only: realistic=-0.531 favorable=-0.531 (n=10)
  mtm_at_horizon: realistic=-0.531 favorable=-0.531 (n=10)
  forced_exit_at_horizon_open: realistic=-0.531 favorable=-0.531 (n=10)
  stop_level_adverse: realistic=-0.531 favorable=-0.531 (n=10)
win rate (closed-only) 3/10
trigger rate 10/14; per-signal expectancy [realistic]=-0.379
entry_bar_weak_close (intraday-touch entries) = 4

