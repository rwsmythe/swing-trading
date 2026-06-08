# Minervini correct-entry exemplar recall (2026-06-08)

**Method record:** ../method-records/minervini-exemplar-recall.md
**Status:** designed; awaiting the operator smoke run.
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
[PLACEHOLDER - populate from exports/research/minervini-exemplar-recall-<ISO>/summary.md at the
operator smoke gate. Include: bucket distribution, screening recall (full + screenable), per-gate
histogram, per-detector recall (faithful + isolated) + Stage-2 delta, specificity contrast.]

## Interpretation
[PLACEHOLDER - a-priori scenarios S1..Sn vs the actual result; implications for cfg-policy
direction; which gate(s) localize the misses.]

## Limitations
L1..Ln per the method record / spec section 12 (archive temporal mutation; SPY-1993; faithful
8/8 TT quirk; irreducible young-name insufficient-history; V1 zigzag-only anchor confound for
cup/HTF; small n -> descriptive only).

## Conclusion
[PLACEHOLDER - verdict + forward directions + V2.1 SIV.D promotion-gate checklist SATISFIED/PENDING.]

## Amendments
- 2026-06-08: shipped with placeholder Results/Interpretation/Conclusion pending the operator run.
