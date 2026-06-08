---
key: minervini-exemplar-recall
name: Minervini correct-entry exemplar recall
layer: monitoring
status: research
baseline_or_predecessor: none
version: 0.1.0
last_updated: 2026-06-08
---

# Minervini correct-entry exemplar recall

## Definition
Point-in-time true-positive recall test (entry side): for each curated Minervini correct-entry
exemplar, does our screen surface it (H1: bucket_for -> aplus/watch) and would any of the 5 V1
detectors fire (H2: geometric_score > 0, class-matched), evaluated strictly <= the locked
entry-crossing session. A miss localizes the silently-rejecting gate. internal.

## Inputs
- Curated exemplar CSV (research/data/minervini-exemplars.csv, curated=yes; 27 of 34).
- Tiingo adjusted daily OHLCV (research/data/tiingo/<symbol>.csv), backward-looking <= asof slice.
- SPY (fallback_spy RS benchmark); VICR via the out-of-harness yfinance materializer.

## Parameters
- window_back=60, window_fwd=5 (positional sweep); control_k=5; bootstrap_b=2000.
- SCREENABLE_FLOOR = 200 + rising_ma_period_days (=221). H2_MIN_BARS=60. CONTROL_GAP_BARS=120.

## Outputs
- results.csv / per_session.csv / summary.md / manifest.json under
  exports/research/minervini-exemplar-recall-<ISO>/. Per-mode recall (full + screenable),
  per-gate first-rejection histogram, per-detector recall (faithful + isolated) + Stage-2 delta,
  Wilson intervals (primary) + ticker-clustered bootstrap (exploratory), same-ticker specificity.

## Operator explainability
- One-sentence rationale: confirms our gates would have caught known-good Minervini setups, and
  localizes which gate silently rejects the misses.
- One-paragraph explanation: The harness replays the production screen and the 5 V1 geometric
  detectors against each documented Minervini correct-entry exemplar, strictly point-in-time at and
  around the locked entry-crossing session (no lookahead: every session slices Tiingo bars <= that
  date). H1 asks whether bucket_for would have surfaced the name (aplus/watch) or skipped it, and
  when it skips a screenable name it attributes the single load-bearing gate (risk / trend-template
  min-passes / trend-template unallowed-miss / vcp) by replaying bucket_for's exact order. H2 asks
  whether the documented detector class fired (geometric_score > 0) under two synthetic Stage-2
  variants - production-faithful (8/8 TT required) and stage-isolated (forced Stage-2) - so the
  isolated-minus-faithful delta attributes a detector miss to the Stage-2 gate versus the detector's
  own geometry. The result is a recall scorecard with Wilson intervals, read against a same-ticker
  negative-control cohort that bounds how specific the firing is to the documented pivot.
- FAQ:
  - Why is the same-ticker control NOT a base rate? The control samples other dates in the SAME
    famous-winner tickers, whose histories contain adjacent bases, follow-on breakouts, and the same
    trend regime. So it answers "does the detector fire specifically at the documented pivot vs at
    other times in this same name," a temporal-specificity contrast - not "how often does the
    detector fire across the market" (a population false-fire rate would need a matched non-exemplar
    cohort, named as a future upgrade).
  - Why does faithful Stage-2 need 8/8 TT? The 5 detectors hard-gate on
    current_stage == "stage_2", which requires a candidates row with 8 trend_template passes -
    stricter than the aplus bucket, which treats TT8 (RS rank) as an allowed miss. This real
    production quirk is surfaced (not hidden) via the faithful-vs-isolated delta.
  - Why is TT8 sometimes NA (P1)? When SPY is missing/pre-1993 or there are too few bars to compute
    the trailing return for both the exemplar and SPY, the RS proxy degenerates to P1: an empty
    returns dict, so compute_rs returns "unavailable" before touching spy_return and TT8 is a
    genuine NA absorbed by allowed_miss_names - a stray SPY value can never fabricate a TT8 verdict.

## Promotion criteria
### Research -> shadow
1. The harness runs end-to-end on the full curated set with the live Tiingo + SPY (+ VICR) archive,
   the manifest records l2_lock_preserved == true, and the study doc Results/Interpretation/
   Conclusion are populated from a real run.
2. The screening-recall and per-detector-recall point estimates plus Wilson intervals are stable
   across two independent archive pulls (archive-mutation sensitivity characterized, not assumed).
### Shadow -> production
1. Not applicable as a deployable artifact: this is a monitoring/diagnostic recall test, not a
   gate. Any deployable finding it surfaces (a gate re-tune, a young-name screen) routes through the
   V2.1 section VII.F source-of-truth correction protocol with its own promotion record - it does
   not promote this harness itself to production.
### Anti-promotion guards
1. L2 LOCK upheld (manifest l2_lock_preserved == true; no yfinance/schwabdev/schwab/ohlcv_archive
   in the evaluator import graph).
2. ZERO production swing/ writes beyond the single CLI registration.
3. Any deployable finding (gate re-tune / young-name screen) routes through the V2.1 SVII.F
   source-of-truth correction protocol, never a direct patch.

## Limitations
L1..Ln per spec section 12 (archive temporal mutation #24/#26; SPY-1993 inception; faithful 8/8 TT
quirk; irreducible insufficient-history young names; V1 zigzag-only anchor; small n descriptive).

## Validation notes
[grows as status advances]

## Changelog
- 2026-06-08 - v0.1.0 - initial record.
