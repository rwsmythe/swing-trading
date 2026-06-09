<!-- research/method-records/minervini-primary-base-recall.md -->
---
key: minervini-primary-base-recall
name: Minervini primary-base (young-name) screen recall
layer: monitoring
status: research
baseline_or_predecessor: minervini-exemplar-recall
version: 0.1.0
last_updated: 2026-06-09
---

# Minervini primary-base (young-name) screen recall

## Definition
Point-in-time true-positive recall + same-ticker temporal-specificity precision test for a Minervini
TWoSMW Ch.11 PRIMARY-BASE screen over young (sub-221-bar) post-IPO names that the original
Trend-Template recall study could not evaluate. For each curated documented-primary-base exemplar,
`screen_at(bars, asof)` asks whether all six Ch.11 criteria hold (history >= ~2mo; a >= ~3wk base by
zigzag swing-high pivot; graduated correction-depth cap by base duration in bars; a FRESH cross to new
high ground, not a recross; and primary = the FIRST base via a first-fire replay), strictly
point-in-time (no lookahead). internal (grounded in TWoSMW Ch.11).

## Inputs
- Curated primary-base cohort (5 ids from research/data/minervini-exemplars.csv; AMZN-1997, BODY, DKS,
  JNPR, YHOO). MELI excluded (young-VCP). Roles: sub_floor vs positive_control.
- Tiingo adjusted daily OHLCV (research/data/tiingo/<symbol>.csv), backward-looking <= asof slice.

## Parameters
- MIN_HISTORY_BARS=40; MIN_BASE_BARS=15; ZIGZAG_THRESHOLD_PCT=3.0; graduated depth caps
  (<=25 bars 0.25 / 26-200 0.35 / >200 0.50); window_back=60, window_fwd=5; control_k=5;
  MAX_CONTROL_AGE_BARS=504; CONTROL_GAP_BARS=120; YOUNG_NAME_CEILING_BARS=221; bootstrap_b=2000.

## Outputs
- results.csv / per_session.csv / summary.md / manifest.json under
  exports/research/primary-base-recall-<ISO>/. Raw recall fractions (sub-floor sweep; day-precision
  single-session BODY-only n=1) FIRST; Wilson as a mechanical interval at n~3; per-criterion
  first-rejection histogram; same-ticker young-window precision contrast (single-session per-anchor
  primary estimand, window best-of reported separately, never conflated); per-exemplar bar count,
  date_precision, eligible_control_count_before_sampling.

## Operator explainability
- One-sentence rationale: confirms a Ch.11 primary-base screen would surface Minervini's documented
  young-name entries the Trend-Template screen structurally cannot evaluate, without firing on random
  young-window dates of the same names.
- One-paragraph explanation: The harness replays a point-in-time Ch.11 primary-base screen against
  each documented young-name primary base, both at the single documented session (day-precision only)
  and across a base window (full documented month for month-precision anchors), and contrasts the
  emergence fire against random young-window same-ticker controls drawn from a pre-filtered
  first-~2-years pool. It is a mechanism-validation proof-of-concept (n~3 evaluable), not a powered
  study; raw fractions are primary and intervals are mechanical.
- FAQ: Why n~3? Codex R1 tightened the cohort (MELI removed as a young-VCP; JNPR history-excluded
  below Minervini's own >=2-month floor). Corpus expansion is the strongly-advised sequel.

## Promotion criteria
### Research -> shadow
1. The harness runs end-to-end on the curated cohort with the live Tiingo archive; the manifest
   records l2_lock_preserved == true; the study Results/Interpretation/Conclusion are populated from a
   real run.
2. Recall point estimates are stable across two independent archive pulls (archive-mutation
   sensitivity characterized, #24/#26).
### Shadow -> production
1. Not applicable: this is a monitoring/diagnostic recall test, not a deployable gate. Any deployable
   young-name screen routes through the V2.1 section VII.F source-of-truth correction protocol.
### Anti-promotion guards
1. L2 LOCK upheld (manifest l2_lock_preserved == true; no yfinance/schwabdev/schwab/ohlcv_archive in
   the evaluator import graph).
2. ZERO production swing/ writes beyond the single CLI registration.
3. Any deployable finding routes through V2.1 section VII.F, never a direct patch.

## Limitations
L1..L7 per spec section 10 (tiny n~3 proof-of-concept; thresholds are operationalizations of Ch.11
prose; same-ticker control only; #24/#26 archive temporal mutation; research-only; zigzag
parameterization + constructive-consolidation-near-ATH gap; single-session vs window estimand
separation).
L8 (month-precision evaluability anchor): evaluable/history-excluded classification is keyed to
bars_through_anchor at the parsed first-of-month anchor while recall sweeps the full documented
month; correct for the current cohort (AMZN 75 / DKS 115 bars, both >> 40), an edge only for a
future month-precision exemplar with <40 bars at month-start; revisit in corpus expansion. A missing
Tiingo archive is reported as data-unavailable (its own summary stratum), never as below-minimum.

## Validation notes
[grows as status advances]

## Changelog
- 2026-06-09 - v0.1.0 - initial record (harness shipped; awaiting operator smoke run).
