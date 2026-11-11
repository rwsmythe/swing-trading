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
total_detections=8770 collapsed_duplicate=7016 unique_signals=1754

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
HEADLINE realistic closed-only mean R=-0.301 (n=1061)
  closed_only: realistic=-0.301 favorable=-0.189 (n=1061)
  mtm_at_horizon: realistic=-0.152 favorable=-0.049 (n=1146)
  forced_exit_at_horizon_open: realistic=-0.152 favorable=-0.049 (n=1146)
  stop_level_adverse: realistic=-0.254 favorable=-0.151 (n=1146)
win rate (closed-only) 260/1061
trigger rate 1146/1590; per-signal expectancy [realistic]=-0.110
entry_bar_weak_close (intraday-touch entries) = 654

## Near-A+ defensible: extension test
HEADLINE realistic closed-only mean R=-0.122 (n=15)
  closed_only: realistic=-0.122 favorable=-0.110 (n=15)
  mtm_at_horizon: realistic=-0.024 favorable=-0.013 (n=16)
  forced_exit_at_horizon_open: realistic=-0.024 favorable=-0.013 (n=16)
  stop_level_adverse: realistic=-0.114 favorable=-0.103 (n=16)
win rate (closed-only) 6/15
trigger rate 16/19; per-signal expectancy [realistic]=-0.020
entry_bar_weak_close (intraday-touch entries) = 8

