# Shadow-Expectancy Engine

Study date: 2026-06-09
Method record: [../method-records/shadow-expectancy-engine.md](../method-records/shadow-expectancy-engine.md)
Status: infrastructure landed; first evidence run pending an accumulated v22 temporal log.

## Question

What per-hypothesis expectancy (mean R-multiple) does each emitted pattern-detection
signal produce when forward-walked through ONE fixed, mechanical management ruleset, and
how fast does that evidence accumulate relative to hand-trading the same signals?

The engine exists to accelerate evidence for the 4-hypothesis program (A+ baseline,
Near-A+ extension, Sub-A+ VCP-not-formed, Capital-blocked) by simulating EVERY emitted
temporal-log signal at signal-pace, instead of waiting on the operator's hand-traded
sample to fill. The output is mechanical-ruleset shadow evidence: it is NOT the operator's
realized hand-traded P&L and must never be co-mingled with the live trade log.

## Null hypothesis

The mechanical ruleset produces no positive per-hypothesis edge: each hypothesis's
realistic-arm, closed-only mean R-multiple is indistinguishable from zero (or from the A+
baseline, for the relative hypotheses) once the honesty sample floor is met. A null result
is a real result here -- it tells the research director the mechanical proxy does not
support deploying that hypothesis on its own.

## Methodology

Read-only consumer of the frozen v22 temporal log (`pattern_detection_events` +
`pattern_forward_observations`), joined to per-run `candidates` rows. No production schema
change (v24 holds); the harness opens the DB with a `mode=ro` URI and never writes.

1. Enumerate `source='pipeline'` detections; group by `(pipeline_run_id, ticker)` and
   collapse each group to ONE canonical signal (the detection whose pivot equals the joined
   candidate pivot at tick precision; consistency gates over the WHOLE group reject a group
   whose frozen forward series or first trigger session diverges).
2. Attribute the joined candidate to the active hypothesis registry via the production
   `match_candidate_to_hypotheses` matcher (exactly-one-match flows on; zero, more-than-one,
   or a missing/unmatched join are recorded as per-reason counters inside a single
   `unattributed` funnel bucket).
3. Forward-walk the canonical signal's FROZEN observation bars through the simulator: a
   single entry fill at `max(pivot, entry_bar.open)`; a MECHANICAL initial stop at
   `entry_bar.low`; a Day-3 50% partial; a breakeven stop raise at +1R; a maturity-staged
   10/20-MA close-below trail; a 126-session horizon. Exits are priced on a
   [realistic, favorable_reprice] bracket; multi-leg R uses ONE fixed denominator
   (`risk_per_share * initial_shares`).
4. Aggregate per hypothesis: trigger rate, per-signal expectancy, and a closed-only headline
   mean R plus four censoring scenarios (closed_only, mtm_at_horizon,
   forced_exit_at_horizon_open, stop_level_adverse). Win rate carries a Wilson interval;
   profit factor / expectancy are suppressed below the sample floor.

A two-level denominator funnel (detection -> collapsed -> unique signal; signal ->
attributed -> terminal status) reconciles exactly: the sum of unattributed reason counts
plus the per-hypothesis terminal-status counts equals the unique-signal count.

## Results

No evidence run is reported yet: the v22 temporal log has not accumulated enough emitted
forward-walked signals to clear the honesty sample floor for any hypothesis. This study
records the LANDED INFRASTRUCTURE and the reproducible artifact contract
(`exports/research/shadow-expectancy-<ISO>/` -> summary.md + manifest.json + results.csv +
per_session.csv). Re-run `swing diagnose shadow-expectancy --db <swing.db>` once the log has
matured; the manifest's funnel + scorecard carry the numeric findings.

## Limitations

- Mechanical-ruleset shadow evidence is a PROXY, not the operator's realized edge: the fixed
  ruleset is one path through management-decision space, not the operator's discretionary
  hand-trading. A positive shadow expectancy is necessary-not-sufficient for deployment.
- The initial stop is the entry bar's low-of-day (a mechanical proxy), not a structural
  stop; same-bar entry/stop ambiguity is reported separately via the same-bar-adverse
  sensitivity.
- MA-trail uses frozen forward closes only (no look-ahead), so early signals with fewer than
  20 forward bars cannot stage to the slow-MA trail.
- The favorable_reprice arm is a NON-EXECUTABLE upper bound, not an achievable fill.
- Open-at-horizon trades are censored; the four scenarios bound (they do NOT point-estimate)
  the open remainder's contribution.

## Conclusion

The shadow-expectancy engine is a landed, reproducible, read-only research surface that will
accumulate per-hypothesis mechanical expectancy at signal-pace. It does not yet report a
deployable finding; it is the instrument, and the first numeric verdict awaits a matured
temporal log. Treat its output as mechanical-ruleset shadow evidence feeding the research
director's deploy/hold decision, never as live hand-traded performance.
