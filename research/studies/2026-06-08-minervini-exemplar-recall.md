# Minervini correct-entry exemplar recall (2026-06-08)

**Method record:** ../method-records/minervini-exemplar-recall.md
**Status:** COMPLETE - operator smoke run executed 2026-06-09 (run `...-20260609T021301Z`).
**Target duration:** per V2.1 SIII.7 time budget.

## Question
Given Minervini's documented correct-entry exemplars, would our screen have surfaced each
(H1) and would any of the 5 V1 detectors have fired (H2), evaluated strictly point-in-time at/
around the locked entry-crossing session? A pass = our gates would have caught a known-good
setup; a miss localizes the silently-rejecting gate.

## Null hypothesis
H0: detector firing at the documented pivot is no more frequent than at random same-ticker
non-entry dates (the temporal-specificity contrast); and the screen surfaces no more than the
screenable-subset base would by construction. (Descriptive; no inferential test claimed.)

## Baseline
Descriptive recall + per-gate first-rejection attribution + same-ticker negative-control cohort
(temporal-specificity contrast, NOT a population base rate).

## Methodology
- Harness: research/harness/minervini_exemplar_recall/ (Approach A thin modules over pure leaves).
- CLI: swing diagnose minervini-recall (no --db; equity = 7500 floor; synthetic stage DB).
- H1: evaluate_one -> bucket; taxonomy {no_data, skip_insufficient_history, surfaced_aplus,
  surfaced_watch, skip_gate_rejection}; load-bearing-gate attribution replays bucket_for order.
- H2: generate_candidate_windows zigzag_pivot -> windows[-1] -> 5 detectors geometric-only,
  both stage variants (production-faithful 8/8-TT vs stage-isolated forced); Stage-2 delta.
- Timing: single-session + [entry-60bd, entry+5bd] positional sweep best-of.
- Uncertainty: Wilson (primary, screenable subset) + ticker-clustered bootstrap (exploratory).

## Results
Run: `exports/research/minervini-exemplar-recall-20260609T021301Z/` (2026-06-09; 27 curated
exemplars; SPY 1993-01-29.. fetched; VICR materialized 1990-04-03..). 20 screenable / 7
insufficient-history; n=20 for the Wilson primary interval.

**Screening recall (H1) - timing-dependent.**

| metric | single-session | window-sweep |
|---|---|---|
| recall (full set, /27) | 0.185 | 0.667 |
| recall (screenable, /20) | 0.250 | **0.900** |
| Wilson 95% (screenable, PRIMARY) | [0.112, 0.469] | [0.699, 0.972] |
| ticker-clustered bootstrap 95% (exploratory) | [0.050, 0.450] | [0.750, 1.000] |
| bucket distribution | watch 5 / skip_gate 15 / insuff 7 | aplus 2 / watch 16 / skip_gate 2 / insuff 7 |
| first-rejecting-gate histogram | vcp 14, trend_template 1 | vcp 1, trend_template 1 |
| per-gate pass rate (screenable) | risk 1.00, tt 0.95, **vcp 0.25** | risk 1.00, tt 0.95, **vcp 0.90** |

**Detector recall (H2) - faithful (Stage-2 8/8-TT) vs stage-isolated.** (`(fired, mapped)`.)

| class | single faithful | single isolated | sweep faithful | sweep isolated | sweep Stage-2 delta |
|---|---|---|---|---|---|
| vcp | 0/12 | 1/12 | **4/12** | **9/12** | +0.417 |
| cup_with_handle | 0/3 | 1/3 | 0/3 | 1/3 | +0.333 |
| flat_base | 0/2 | 0/2 | 0/2 | 0/2 | 0.000 |
| double_bottom_w | 0/2 | 0/2 | 0/2 | 0/2 | 0.000 |

**Same-ticker specificity contrast (control; n=135, mapped=95; NOT a population base rate).**

| rate | single-session | window-sweep |
|---|---|---|
| control surfaced (H1) | 0.052 | 0.356 |
| control fired faithful (H2) | 0.021 | 0.126 |
| control fired isolated (H2) | 0.147 | 0.789 |

## Interpretation
1. **Timing is the dominant variable for screening recall, exactly as the dual-mode design
   predicted (spec section 6).** At the single breakout session the screen surfaces only 5/20
   screenable exemplars, and 14 of the 15 gate-rejections localize to **VCP** (per-gate VCP pass
   rate 0.25): at the pivot the stock is extended / wide-range, so the proximity-to-20MA and
   tightness gates fail *by construction*. Evaluated across the [entry-60bd, entry+5bd] base window,
   recall jumps to **18/20 (0.90, Wilson [0.70, 0.97])** and the VCP pass rate recovers to 0.90 -
   the screen catches the setup *during the tight consolidation*, not at the breakout. The recall
   number is meaningful only with the window-sweep timing; single-session materially under-counts.
2. **The young-name insufficient-history floor is real and irreducible.** Exactly 7/27 exemplars
   (QSII, JNPR, AMZN-1997, MELI, BODY, and 2 others) are `skip_insufficient_history` in BOTH modes -
   they lack ~221 trading days at entry because the stock was newly public. No threshold tuning
   closes this; it caps full-set recall at 20/27. This is the codified-Trend-Template vs
   Minervini-buys-young-leaders tension, surfaced cleanly rather than mislabeled as a gate rejection.
3. **With correct timing, the residual screening miss is narrow.** Only 2 screenable exemplars are
   gate-rejected across the window (one VCP, one trend_template). The screen is *not* systematically
   blind to documented setups; the apparent low single-session recall is a timing artifact, not a
   gate-tuning deficiency.
4. **The detector layer's recall is bounded by the Stage-2 8/8-TT gate, and that gate is what makes
   it specific.** Production-faithful VCP fires 4/12 in the window-sweep; stage-isolated fires 9/12
   (Stage-2 delta +0.42) - so the 8/8-TT Stage-2 requirement (stricter than the aplus bucket, which
   treats TT8 as an allowed miss) gates off roughly half the VCP geometry fires. But the
   specificity contrast shows *why that gate matters*: the stage-isolated detector fires on **79%**
   of random same-ticker control windows (non-specific), whereas the production-faithful detector
   fires on 12.6% of controls vs 33% at the exemplars (~2.6x). The Stage-2 gate is the source of the
   detector's discrimination; removing it makes geometry fire almost everywhere.
5. **cup_with_handle / high_tight_flag are anchor-mode-limited (spec 12.9).** cup fires 0/3 faithful
   and only 1/3 even stage-isolated; there are 0 curated HTF exemplars. V1's zigzag-only
   (swing-low) window anchor under-serves these swing-high-anchored patterns, so their near-zero
   recall reflects the deployed anchor mode, not necessarily the detector geometry. n is tiny.

## Limitations
L1..Ln per the method record / spec section 12 (archive temporal mutation; SPY-1993; faithful
8/8 TT quirk; irreducible young-name insufficient-history; V1 zigzag-only anchor confound for
cup/HTF; small n -> descriptive only).

## Conclusion
**Verdict (descriptive; small n; no inferential test claimed).** Our screen would have surfaced
**90% (18/20) of the screenable** documented Minervini correct-entry exemplars to aplus/watch when
evaluated point-in-time across the base window - strong recall against known-good setups. Two facts
qualify it: (a) the breakout-bar (single-session) view under-counts to 25% because VCP tightness/
proximity fail by design at the extended pivot - so timing choice, not gate tuning, drives the
headline number; and (b) 7/27 exemplars are structurally un-screenable (newly-public, <~221 bars).
The detector layer's recall is real but gated: the Stage-2 8/8-TT requirement suppresses ~half the
VCP geometry fires, while simultaneously being the source of the detectors' specificity.

**Forward directions (all route through V2.1 SVII.F source-of-truth correction, NOT a direct patch).**
- A **young-name screening variant** for sub-221-bar post-IPO leaders is the highest-value follow-up
  (own future arc); the current screen cannot evaluate them at all.
- Whether the **Stage-2 detector gate should require 8/8 TT** (stricter than the aplus bucket's
  TT8-allowed-miss) is a genuine open cfg/methodology question this study surfaced; the faithful-vs-
  isolated delta quantifies its cost (+0.42 VCP) and the control contrast quantifies its benefit
  (specificity). A deliberate decision, not an accident, but worth ratifying.
- **Class-appropriate window anchoring** for cup_with_handle / high_tight_flag (swing-high anchors)
  would let those classes be fairly measured; V1's zigzag-only anchor cannot.

**Promotion-gate (V2.1 SIV.D).** This arc is **methodological-infrastructure + diagnostic**, NOT a
deployable ruleset change. No production gate is re-tuned here; promotion gate **N/A / not invoked**.
Any future gate change driven by these findings must route through the correction protocol.

## Amendments
- 2026-06-08: shipped with placeholder Results/Interpretation/Conclusion pending the operator run.
- 2026-06-09: operator smoke run executed (run dir `...-20260609T021301Z`); Results/Interpretation/
  Conclusion populated from `summary.md`. VICR materialized (yfinance >=1990); SPY pulled (Tiingo).
