# Shadow-expectancy engine - summary

Mechanical-ruleset SHADOW evidence (NOT live hand-traded counts; spec 1).

## OHLC epsilon-clamp (reader-side; log untouched; brief 2b)
  clamped_bar_count=92 clamped_bar_events=249 (<= 1.0% shape tolerance)
    ADEA 2026-07-13 clamp=0.9754%
    AMN 2026-07-13 clamp=0.0294%
    AMN 2026-07-16 clamp=0.1900%
    APLE 2026-07-16 clamp=0.1928%
    BWA 2026-07-22 clamp=0.2724%
    CALY 2026-07-10 clamp=0.4348%
    CARR 2026-07-22 clamp=0.2056%
    COLD 2026-07-17 clamp=0.0628%
    COLD 2026-07-30 clamp=0.2766%
    COLD 2026-07-31 clamp=0.4613%
    CTOS 2026-07-08 clamp=0.1027%
    CTOS 2026-07-22 clamp=0.4653%
    CTOS 2026-07-28 clamp=0.1932%
    CUZ 2026-07-28 clamp=0.1892%
    CXW 2026-07-20 clamp=0.1570%
    DINO 2026-06-10 clamp=0.3392%
    DINO 2026-06-18 clamp=0.4186%
    DINO 2026-07-01 clamp=0.3377%
    DINO 2026-07-08 clamp=0.1908%
    DK 2026-07-20 clamp=0.2632%

## Denominator funnel (detection-level)
total_detections=3890 collapsed_duplicate=3112 unique_signals=778

## Unattributed signals (pre-/non-attribution; spec 7.1)
  no_candidate_join=0
  matched_no_hypothesis=0
  multi_match=0
  inconsistent_detection_series=0
  total_unattributed=0

## A+ baseline
HEADLINE realistic closed-only mean R=-0.186 (n=3) [SUPPRESSED n<floor]
  closed_only: realistic=-0.186 favorable=-0.186 (n=3)
  mtm_at_horizon: realistic=-0.186 favorable=-0.186 (n=3)
  forced_exit_at_horizon_open: realistic=-0.186 favorable=-0.186 (n=3)
  stop_level_adverse: realistic=-0.186 favorable=-0.186 (n=3)
win rate (closed-only) 1/3
trigger rate 3/4; per-signal expectancy [realistic]=-0.139
entry_bar_weak_close (intraday-touch entries) = 1

## Broad-watch baseline
HEADLINE realistic closed-only mean R=-0.212 (n=347)
  closed_only: realistic=-0.212 favorable=-0.140 (n=347)
  mtm_at_horizon: realistic=-0.164 favorable=-0.096 (n=371)
  forced_exit_at_horizon_open: realistic=-0.164 favorable=-0.096 (n=371)
  stop_level_adverse: realistic=-0.223 favorable=-0.155 (n=371)
win rate (closed-only) 85/347
trigger rate 371/706; per-signal expectancy [realistic]=-0.086
entry_bar_weak_close (intraday-touch entries) = 207

## Near-A+ defensible: extension test
HEADLINE realistic closed-only mean R=0.443 (n=2) [SUPPRESSED n<floor]
  closed_only: realistic=0.443 favorable=0.443 (n=2)
  mtm_at_horizon: realistic=0.443 favorable=0.443 (n=2)
  forced_exit_at_horizon_open: realistic=0.443 favorable=0.443 (n=2)
  stop_level_adverse: realistic=0.443 favorable=0.443 (n=2)
win rate (closed-only) 2/2
trigger rate 2/2; per-signal expectancy [realistic]=0.443
entry_bar_weak_close (intraday-touch entries) = 0

