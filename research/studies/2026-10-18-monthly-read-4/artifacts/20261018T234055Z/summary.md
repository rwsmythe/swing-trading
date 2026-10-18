# Shadow-expectancy engine - summary

Mechanical-ruleset SHADOW evidence (NOT live hand-traded counts; spec 1).

## OHLC epsilon-clamp (reader-side; log untouched; brief 2b)
  clamped_bar_count=230 clamped_bar_events=910 (<= 1.0% shape tolerance)
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
    AVTR 2026-10-14 clamp=0.0637%
    BAX 2026-08-17 clamp=0.1158%
    BAX 2026-09-22 clamp=0.2280%
    BCS 2026-08-19 clamp=0.0037%
    BCS 2026-08-26 clamp=0.0369%

## Denominator funnel (detection-level)
total_detections=7675 collapsed_duplicate=6140 unique_signals=1535

## Unattributed signals (pre-/non-attribution; spec 7.1)
  no_candidate_join=0
  matched_no_hypothesis=0
  multi_match=0
  inconsistent_detection_series=0
  total_unattributed=0

## A+ baseline
HEADLINE realistic closed-only mean R=-0.590 (n=7)
  closed_only: realistic=-0.590 favorable=-0.580 (n=7)
  mtm_at_horizon: realistic=-0.590 favorable=-0.580 (n=7)
  forced_exit_at_horizon_open: realistic=-0.590 favorable=-0.580 (n=7)
  stop_level_adverse: realistic=-0.590 favorable=-0.580 (n=7)
win rate (closed-only) 1/7
trigger rate 7/12; per-signal expectancy [realistic]=-0.344
entry_bar_weak_close (intraday-touch entries) = 4

## Broad-watch baseline
HEADLINE realistic closed-only mean R=-0.377 (n=902)
  closed_only: realistic=-0.377 favorable=-0.269 (n=902)
  mtm_at_horizon: realistic=-0.241 favorable=-0.138 (n=948)
  forced_exit_at_horizon_open: realistic=-0.241 favorable=-0.138 (n=948)
  stop_level_adverse: realistic=-0.349 favorable=-0.247 (n=948)
win rate (closed-only) 203/902
trigger rate 948/1357; per-signal expectancy [realistic]=-0.168
entry_bar_weak_close (intraday-touch entries) = 547

## Near-A+ defensible: extension test
HEADLINE realistic closed-only mean R=-0.369 (n=14)
  closed_only: realistic=-0.369 favorable=-0.357 (n=14)
  mtm_at_horizon: realistic=-0.145 favorable=-0.133 (n=15)
  forced_exit_at_horizon_open: realistic=-0.145 favorable=-0.133 (n=15)
  stop_level_adverse: realistic=-0.318 favorable=-0.306 (n=15)
win rate (closed-only) 5/14
trigger rate 15/18; per-signal expectancy [realistic]=-0.121
entry_bar_weak_close (intraday-touch entries) = 8

