<!-- research/studies/2026-06-09-minervini-primary-base-recall.md -->
# Minervini primary-base (young-name) screen recall (2026-06-09)

**Method record:** ../method-records/minervini-primary-base-recall.md
**Status:** SHIPPED - awaiting operator smoke run (Results/Interpretation/Conclusion are placeholders).
**Target duration:** per V2.1 SIII.7 time budget.

## Question
Does a point-in-time Minervini Ch.11 PRIMARY-BASE screen surface (recall) the documented young-name
primary-base emergences that the Trend-Template recall study found structurally un-screenable
(< ~221 bars, newly public), while staying selective (precision) against random young-window same-
ticker dates? A pass = the screen catches the documented primary-base emergences without firing
indiscriminately.

## Null hypothesis
H0: the primary-base screen fires at the documented emergence no more frequently than at random
young-window same-ticker control dates (the temporal-specificity contrast). Descriptive; no
inferential test claimed (n~3 proof-of-concept).

## Baseline
Descriptive recall (raw fractions first) + per-criterion first-rejection attribution + same-ticker
young-window precision contrast (single-session per-anchor primary estimand; window best-of separate).

## Methodology
- Harness: research/harness/minervini_primary_base_recall/ (Approach A; new sibling over the FROZEN
  minervini_exemplar_recall leaves + swing.patterns.foundation zigzag).
- CLI: swing diagnose primary-base-recall (no --db; pure on bars).
- Screen (screen_at): Ch.11 criteria 1-6 -- history (>=40 bars); base id via extract_zigzag_swings
  (3% threshold) with calendar->bar mapping; duration (>=15 bars); graduated depth cap by base
  duration in bars; fresh-cross-not-recross emergence; primary = first base via first-fire replay.
- Cohort: {AMZN-1997, BODY, DKS} evaluable sub-floor (n=3) + YHOO positive control + JNPR
  history-excluded (25 bars < 40, below Minervini's own >=2mo floor). MELI excluded (young-VCP).
- Timing: window-sweep reliable for ALL rows (day/exact uses [entry-60bd, entry+5bd]; month uses the
  full documented calendar month + slack); single-session reported ONLY for day-precision (BODY-only,
  n=1).
- Precision: own pre-filtered young-window control sampler ([39,503] BEFORE sampling, then >=120 from
  entry + outside the sweep window + deterministic seed; k=5).
- Uncertainty: raw fractions FIRST; Wilson labeled a mechanical interval at n~3; ticker-clustered
  bootstrap exploratory-only.

## Results
[PLACEHOLDER - populate from exports/research/primary-base-recall-<ISO>/summary.md after the operator
smoke run. Report: sub-floor sweep recall RAW fraction (x/3) + the fired/missed ids; day-precision
single-session BODY-only yes/no; YHOO positive-control fire; JNPR history-exclusion note; per-
criterion first-rejection histogram; same-ticker precision contrast (single-session per-anchor vs
window best-of, never conflated); per-exemplar bar counts + eligible_control_count_before_sampling.]

## Interpretation
[PLACEHOLDER - populate after the run.]

## Limitations
L1..L7 per the method record / spec section 10 (tiny n~3 proof-of-concept; thresholds are
operationalizations of Ch.11 prose; same-ticker control only; #24/#26 archive temporal mutation;
research-only -> V2.1 SVII.F; zigzag parameterization + constructive-consolidation-near-ATH V1 gap;
single-session vs window estimand separation).

## Conclusion
[PLACEHOLDER - populate after the run. Expected framing: mechanism-validation proof-of-concept, NOT a
deployable ruleset change (V2.1 SIV.D promotion gate N/A); corpus expansion
(Google/Starbucks/Reebok/MSFT/Intel/Rambus/RIMM Ch.11 primary bases) is the strongly-advised
immediate sequel.]
Per docs/research-director-context.md (P2), this screen's output is UNVALIDATED until a P1 shadow-
expectancy engine can price its expectancy -- so the deployable recommendation is "expand the corpus +
price via P1," not "deploy."

## Amendments
- 2026-06-09: shipped with placeholder Results/Interpretation/Conclusion pending the operator run.
