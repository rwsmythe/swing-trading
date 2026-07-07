# Shadow-expectancy engine - summary

Mechanical-ruleset SHADOW evidence (NOT live hand-traded counts; spec 1).

## OHLC epsilon-clamp (reader-side; log untouched; brief 2b)
  clamped_bar_count=15 clamped_bar_events=19 (<= 1.0% shape tolerance)
    DINO 2026-06-10 clamp=0.3392%
    DINO 2026-06-18 clamp=0.4186%
    DINO 2026-07-01 clamp=0.3377%
    EVC 2026-06-18 clamp=0.1014%
    M 2026-06-26 clamp=0.0389%
    MFG 2026-06-26 clamp=0.2060%
    NSA 2026-06-26 clamp=0.3302%
    NSA 2026-07-01 clamp=0.5309%
    OGN 2026-07-01 clamp=0.0370%
    RLJ 2026-06-29 clamp=0.2534%
    RSI 2026-07-01 clamp=0.0640%
    TLYS 2026-06-29 clamp=0.7712%
    VIRT 2026-07-01 clamp=0.4698%
    VOYA 2026-07-01 clamp=0.0836%
    VSTS 2026-06-12 clamp=0.1440%

## Denominator funnel (detection-level)
total_detections=1775 collapsed_duplicate=1420 unique_signals=355

## Unattributed signals (pre-/non-attribution; spec 7.1)
  no_candidate_join=0
  matched_no_hypothesis=0
  multi_match=0
  inconsistent_detection_series=0
  total_unattributed=0

## A+ baseline
HEADLINE realistic closed-only mean R=0.000 (n=0) [SUPPRESSED n<floor]
  closed_only: realistic=0.000 favorable=0.000 (n=0)
  mtm_at_horizon: realistic=1.124 favorable=1.124 (n=1)
  forced_exit_at_horizon_open: realistic=1.124 favorable=1.124 (n=1)
  stop_level_adverse: realistic=0.000 favorable=0.000 (n=1)
win rate (closed-only) 0/0
trigger rate 1/2; per-signal expectancy [realistic]=0.562
entry_bar_weak_close (intraday-touch entries) = 1

## Broad-watch baseline
HEADLINE realistic closed-only mean R=-0.637 (n=100)
  closed_only: realistic=-0.637 favorable=-0.564 (n=100)
  mtm_at_horizon: realistic=0.551 favorable=0.594 (n=171)
  forced_exit_at_horizon_open: realistic=0.551 favorable=0.594 (n=171)
  stop_level_adverse: realistic=-0.057 favorable=-0.014 (n=171)
win rate (closed-only) 11/100
trigger rate 171/285; per-signal expectancy [realistic]=0.331
entry_bar_weak_close (intraday-touch entries) = 95

