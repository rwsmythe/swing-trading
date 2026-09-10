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
total_detections=6510 collapsed_duplicate=5208 unique_signals=1302

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
HEADLINE realistic closed-only mean R=-0.376 (n=655)
  closed_only: realistic=-0.376 favorable=-0.281 (n=655)
  mtm_at_horizon: realistic=-0.295 favorable=-0.207 (n=712)
  forced_exit_at_horizon_open: realistic=-0.295 favorable=-0.207 (n=712)
  stop_level_adverse: realistic=-0.352 favorable=-0.264 (n=712)
win rate (closed-only) 142/655
trigger rate 712/1147; per-signal expectancy [realistic]=-0.183
entry_bar_weak_close (intraday-touch entries) = 422

## Near-A+ defensible: extension test
HEADLINE realistic closed-only mean R=-0.400 (n=11)
  closed_only: realistic=-0.400 favorable=-0.400 (n=11)
  mtm_at_horizon: realistic=-0.346 favorable=-0.346 (n=12)
  forced_exit_at_horizon_open: realistic=-0.346 favorable=-0.346 (n=12)
  stop_level_adverse: realistic=-0.450 favorable=-0.450 (n=12)
win rate (closed-only) 4/11
trigger rate 12/18; per-signal expectancy [realistic]=-0.231
entry_bar_weak_close (intraday-touch entries) = 5

