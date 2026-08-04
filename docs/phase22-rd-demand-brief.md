# Phase 22 — RD capability demand

**From:** RD. **To:** CHARC (who owns phase scoping and sequencing — this is DEMAND, not a scope doc).
**Banked:** 2026-08-01, operator-directed, in preparation for execution **after Phase 21 completes**.
**Status:** not commissioned. Sequencing, decomposition into arcs, and tripwire passes are CHARC's.

---

## The through-line

Every item below serves one property: **a result can state what it was computed from.**

That is not a theme chosen for tidiness — it is what the August monthly read cost us. T4's CONFIRMED-NEGATIVE verdict was withdrawn because a number was read off a substrate whose maturity nobody could see, and the same week produced three more instances of the identical shape: a run-level stamp standing in for a per-row fact, an order-entered date standing in for an execution date, and three surfaces computing one order price three different ways.

---

## 1. ENTRY-LIMIT DISPLAY + SHADOW EMIT — the ORDER half is SETTLED and closed

**RESOLVED 2026-08-03 (operator ruling, put to him in RD's terms):** the canonical framework order price is the **zone cap, everywhere, one source**. The operator explicitly RETIRED his 2026-04-25 one-percent pure-trigger discipline, knowing it is a loosening — RD's explicit-call condition met. `chase_factor` aligns to the cap via a CHARC-dispatched rider (single-source over a second constant; comment replaced not annotated; full suite; at-or-after the 21-B merge). The one-canonical-price-at-merge constraint is satisfied.

**What remains for Phase 22 — display and measurement only:**
- **The zone-range render:** the dashboard may render the buy zone as a RANGE (pivot → cap) rather than a single number — the zone IS a range in the doctrine, and one number implies precision the method does not claim. Design question for the surface, no longer coupled to any order semantics.
- **REMOVE the `chase_factor` knob — BOTH DIRECTORS ALIGNED 2026-08-03 (independent, convergent posts two seconds apart); operator RATIFIES at scoping.** Default, validation, override path, and the web editor row all go. After the 04-25 retirement the knob encodes no doctrine — it is a second framework constant waiting to disagree with the first, and its web editor is a supported re-divergence path no price-rendering grep will find (the item-6 drift class institutionalized as a feature). Its only remaining function is recreating a state the operator himself filed as a bug. One coherent surface story: the dashboard renders the zone from the single source, and the knob that used to approximate it goes away. **Fallback if the operator declines:** a non-default value must render VISIBLY as his override, never as an unmarked framework number. **OPERATOR RULED 2026-08-03: NO KNOB, 3% canonical** — removal proceeds; his one carried question is whether the canonical value lives in CONFIG for tunability. **The pin for scoping (orchestrator's, adopted): the defect was never CONFIGURABILITY, it was TWO SOURCES — a config-backed single source both surfaces read satisfies every ruling; a second independently-editable field does not.** **Delete WITH the knob:** the rider's override-DISCLOSURE block + its two tests (dead conditional once the knob goes — a guard outliving its condition), and the 21-B §D.3 sizing-divergence disclosure + `nightly_recommendation_shares` delta render + tests once the sizing-basis fix lands (same class). **Also on this item's checklist: revisit the one-cent fill-attribution exemption when the display-era fills age out.**
- **Emit `entry_fill` and `pivot` in the shadow engine's `results.csv`** (values the simulator already holds). Makes the uncapped-fill divergence measurable and enables the curve surface (§3). **Do NOT change the engine's fill rule** — that touches the measurement chain and breaks T4 comparability. Measure first.

## 2. CAPTURE-BASIS — a SECOND immutable log set (operator's design, adopted over mine)

**The problem:** analyses needing pre-detection bars must read the OHLCV archive, which is MUTABLE. Measured drift, 4,172 frozen-vs-archive comparisons: **88.06% identical, median 0.000000%, p95 0.048%, max 2.028%, 0.91% above 0.5%.** So drift is **rare but real** — which also corrects gotcha #26's "0.5–3%", a figure that reads as though drift were typical.

**The design (operator's, and it beats the `capture_basis` tag I proposed):** a SEPARATE immutable log set for retrieved-for-calculation data, with a read cascade — primary log → backfill log → archive.

**Why it wins:** **no write path touches the primary log at all.** My version needed a second writer on the immutable log with different semantics; his leaves the primary's writer set unchanged, which **fully clears the 2026-06-13 no-backfill precedent** instead of arguing around it. Separation by construction, not by convention.

**Three RD requirements:**
1. **Tier 3 is a MATERIALIZATION source, never a COMPUTATION path.** An analysis either finds its bars in tiers 1–2, or materializes what is missing into tier 2 and then reads. That makes "ran off immutable data" structural rather than claimed, and prevents a mutable read being laundered into something that looks logged.
2. **`captured_at` per row.** The second log makes backfilled data HONEST, not ACCURATE — a 2026-06 bar captured today is still today's possibly-2%-drifted value. Nobody should later read tier 2 as equivalent to tier 1.
3. **Redundant materialization becomes a free drift gauge.** If something tries to materialize a bar tier 1 already holds, **do not write — record the comparison.** The standing drift monitor falls out of the cascade at zero cost. Also record WHICH analysis requested each materialization, so tier 2 cannot accumulate orphan rows.

## 3. THE CURVE SURFACE — GUI, and a retention constraint that blocks it

**Two curves, named distinctly, both rendered:**
- **Expectancy convergence curve** (fixed cohort, x = cohort age in NYSE sessions) — the estimator that converges. Its asymptote is the expectancy.
- **Running expectancy-to-date** (from epoch, all cohorts) — what the population HAS produced. Operationally real and better for monitoring, but it converges to *expectancy minus a steady-state censoring bias*, not to the expectancy.

**They must not be visually or nominally confusable** — substituting the second for the first is precisely what produced the withdrawn verdict.

**Requirements:** render each population as a **BAND** between `closed_only` and `mtm` (the censoring bracket) rather than a line — the band width IS the confidence, drawn, and it makes a point-verdict read off a wide band structurally hard. **Y-axis labelled "estimated mean R", never "expectancy."** Age-indexed x only. **No fitted asymptote or trend extrapolation.** Respect the engine's n-floor suppression. Placement is an evaluation surface, not the trading dashboard.

**Population selection with a pre-registration guardrail (RD-imposed):** preset populations are **pre-registered** — a fixed named list; ad-hoc cuts are permitted but rendered **EXPLORATORY** and are not citable as evidence. An arbitrary filter builder over outcomes is a p-hacking machine.

**THE BLOCKING CONSTRAINT:** `_SHADOW_EXPECTANCY_KEEP = 90` — the artifact series is pruned and gitignored. The convergence curve is built from that series, so **the June curve's −1.0000 start expires around November.** Either retention changes for this data or the curve's inputs are materialized durably. Same problem v2.1's cite=commit solved for one-off citations, now needing a solution for a continuous surface.

**Small enabler:** emit `entry_fill` and `pivot` in `results.csv` (values the simulator already holds). Makes the shadow's uncapped-fill divergence measurable. **Do NOT change the engine's fill rule** — that touches the measurement chain and breaks T4 comparability.

## 4. CARRIED FROM PHASE 21

- **Latch `criteria_lapsed` amendment** (routed `20260801T145240Z`) — a 5th clear reason with a DIRECTIONAL conjunct, because the obvious form would have destroyed FTRE.
- **Schwab auto-fill entry-date defect + the missing correction surface** (routed `20260801T145327Z`) — mapper takes the order's ENTERED date; D19-class gap, four live symptoms, an H1-cohort row currently wrong.
- **A-4 dedicated `discrepancy_type`** — already banked at the Phase-20 close; discrepancy 95 is the evidence (a "price mismatch" with a **$0.0000** delta and `candidate_count: 1` under `multi_match_within_window`).

## 5. RD-OWNED, NOT ENGINEERING

- **Watch-standard amendment: a MATURITY GATE on T4-class decision reads** — bracket width below the distance from the estimate to the decision boundary, AND cohort age past the winner-resolution window. Read-discipline, not code. Mine to draft.

## 6. TRIPWIRES + SEQUENCING

Item 2 is new schema plus arguably a new standing process; item 3 touches web + possibly retention policy. **CHARC's architecture pass required; decomposition into arcs and ordering are CHARC's call.** Item 1 is the only one with a hard deadline attached to Phase 21.

**Standing constraint that shapes all of it, established 2026-08-01:** the finviz screen must stay WIDE and filtering must happen downstream. A screen narrowed later can always be re-tested by subsetting the log; a screen narrowed NOW forecloses every future question about what it excluded. Widening cannot be back-tested — the log contains only what the screen admitted.
