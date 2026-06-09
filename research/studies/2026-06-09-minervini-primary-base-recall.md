<!-- research/studies/2026-06-09-minervini-primary-base-recall.md -->
# Minervini primary-base (young-name) screen recall (2026-06-09)

**Method record:** ../method-records/minervini-primary-base-recall.md
**Status:** COMPLETE - smoke run executed 2026-06-09 (run `...-20260609T102009Z`).
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
Run: `exports/research/primary-base-recall-20260609T102009Z/` (2026-06-09; local Tiingo archive).

**Recall (sub-floor evaluable {AMZN-1997, BODY, DKS}).**
- sub-floor window-sweep recall (RAW): **3/3** — all fired (AMZN-1997, BODY, DKS); none missed.
  Wilson 95% [0.438, 1.000] (mechanical at n=3); ticker-clustered bootstrap [1.000, 1.000] (exploratory).
- day-precision single-session (BODY-only, n=1): **1/1**.
- sweep first-rejecting-criterion histogram: `{}` (no sub-floor misses).

**Positive control (YHOO, sufficient-history documented primary base).**
- window-sweep **fired = False**, `first_rejecting_criterion = depth` — the screen **missed** a known
  documented primary base, rejecting it because the base's correction exceeded the graduated depth cap.

**Below-minimum (reported, not a screen miss).** JNPR `history`-excluded (25 bars < 40, below
Minervini's own ≥2-month floor). **Data unavailable:** none.

**Precision (same-ticker young-window control; single-session per-anchor PRIMARY, window SEPARATE).**

| exemplar | role | control single (PRIMARY) | control window (SEPARATE) | k / eligible | exemplar single / window |
|---|---|---|---|---|---|
| AMZN-1997 | sub_floor | 0.000 | 0.000 | 5 / 309 | None (month) / True |
| BODY | sub_floor | 0.000 | 0.000 | 5 / 328 | True / True |
| DKS | sub_floor | 0.000 | 0.000 | 5 / 270 | None (month) / True |
| YHOO | positive_control | 0.000 | 0.000 | 5 / 226 | False / False |

**Control fire rate = 0.000 across every name, both estimands** — the screen fired at the documented
emergences (3/3 sub-floor) and at **none** of the random young-window control sessions.

## Interpretation
1. **The mechanism validates on the sub-floor cohort, with perfect same-ticker specificity.** The
   Ch.11 primary-base criteria, operationalized point-in-time, fired on **all 3** evaluable sub-floor
   documented primary bases (AMZN-1997, BODY, DKS) at their documented emergences — and on **zero**
   of the same-ticker young-window control sessions (control fire 0.000, single AND window, all four
   names). So on this tiny set the screen is both sensitive (3/3) and highly selective (0% control
   fire): it recognizes the documented primary-base emergence and does not fire at random other young
   sessions of the same names. That is the core proof-of-concept result.
2. **The positive control (YHOO) FAILED on `depth` — the most important diagnostic.** YHOO 1997 is a
   documented *sufficient-history* primary base (Fig 11.3), the sanity check that the screen fires on
   a known full-history primary base. It did **not** — rejected because the base's correction exceeded
   the graduated depth cap. Either the **depth-cap ladder is mis-calibrated** for YHOO's base (its
   documented correction was deeper than the cap allowed at its duration bucket — Minervini permits up
   to ~50% for ~1yr bases, so the bar→duration→cap mapping may under-allow), or the **base-bounding**
   picked the wrong `base_high`/`base_low`. At n=1 it is a single data point, but it is a real flag:
   the screen's depth operationalization rejects at least one documented primary base. This is exactly
   the calibration signal the corpus-expansion sequel is for.
3. **n is tiny (3 sub-floor + 1 control).** 3/3 + 0% specificity is encouraging but **illustrative** —
   Wilson [0.44, 1.00] at n=3 is uninformative as an interval. The deliverable is mechanism-validation
   + the YHOO depth flag, not a powered recall estimate.

## Limitations
L1..L7 per the method record / spec section 10 (tiny n~3 proof-of-concept; thresholds are
operationalizations of Ch.11 prose; same-ticker control only; #24/#26 archive temporal mutation;
research-only -> V2.1 SVII.F; zigzag parameterization + constructive-consolidation-near-ATH V1 gap;
single-session vs window estimand separation).
L8 (month-precision evaluability anchor): for month-precision exemplars, evaluable/history-excluded
classification is keyed to bars_through_anchor at the PARSED first-of-month anchor (the spec R1.m2
bar count), while recall sweeps the full documented month. For the current cohort this is correct
(AMZN-1997 75 bars, DKS 115 bars -- both far above the 40-bar floor). The only divergent case is a
hypothetical future month-precision exemplar with <40 bars on the 1st but >=40 later in the
documented month; it would be classified history-excluded despite a screenable sweep. None such
exists in the cohort; the strongly-advised corpus-expansion sequel should revisit the stratification
anchor if it adds a name IPO'd ~2 months before its documented month.

## Conclusion
**Verdict (proof-of-concept; n≈3).** The Ch.11 primary-base screen MECHANISM-VALIDATES: it fired on
all 3 evaluable sub-floor documented primary bases with **perfect same-ticker specificity** (0% control
fire, both estimands). The one negative — the **YHOO positive control rejected on `depth`** — is the
load-bearing finding: it shows the depth-cap ladder (or base-bounding) is **not yet calibrated** and
misses at least one documented sufficient-history primary base. So the screen works in principle and is
selective, but its thresholds need tuning before any recall claim generalizes.

**NOT a deployable ruleset change** (V2.1 §IV.D promotion gate N/A). Forward, routed through V2.1
§VII.F: (1) **corpus expansion** (Google/Starbucks/Reebok/MSFT/Intel/Rambus/RIMM Ch.11 primary bases)
is the strongly-advised immediate sequel — it both firms n AND supplies the documented bases needed to
**calibrate the depth ladder** (the YHOO miss is the first calibration signal). (2) Per
`docs/research-director-context.md` (P2), this screen's output is **UNVALIDATED until a P1
shadow-expectancy engine can price its expectancy** — so the deployable recommendation is "expand the
corpus + calibrate depth + price via P1," **not "deploy."**

## Amendments
- 2026-06-09: shipped with placeholder Results/Interpretation/Conclusion pending the operator run.
- 2026-06-09: operator/orchestrator smoke run executed (run `...-20260609T102009Z`, local Tiingo
  archive); Results/Interpretation/Conclusion populated. Headline: 3/3 sub-floor recall + 0% control
  fire (mechanism validates + specific); YHOO positive control rejected on `depth` (depth-ladder
  calibration flag); n≈3 proof-of-concept.
