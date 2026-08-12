# §8.5 wave-close warning-cleanup pass — executed 2026-08-12

**Parent:** `docs/phase21-boundary-paydown-commissioning-brief.md` §8.5 (operator-originated 2026-08-10,
RD-inventoried). **Run after** item 5 + the sweep + D31-exit merge (`5a6d39cd`).

**Binding constraint honoured: the cleanup goes THROUGH the surfaces, not around them.** I resolved
NOTHING. Two rows are a director's ruling, one is an operator action at a broker, and hand-clearing any
of them would waste the machinery built to clear them and leave the ledger unable to say what happened.
**This pass is a verification and a routing, which is what §8.5 actually asks for.**

**Every state below was read from the live DB today, not carried from the inventory.** The inventory
was written 2026-08-10; since then AMN filled, closed at ≈ −0.996R, LQDA and ORKA filled, CADL was
entered, and four reconciliation runs completed. **Two rows have moved and one item exists that the
inventory could not have known about.**

---

## The six inventoried rows, re-derived

| # | warning | inventory said | **live state today** | route |
|---|---|---|---|---|
| 1 | **VSTS latch UNVERIFIABLE** | operator declines + cancels + logs | **STILL OPEN.** `latch_order_intents` holds 3 rows — OII `place`+`validity`, CADL `place`. **Zero `decline` rows**, so the 3a terminal has not been used. | **OPERATOR ACTION** — see below |
| 2 | **discrepancy 95** | "in flight" | **CLOSED** `journal_corrected`, resolved 2026-08-11T05:38, correction 38, reason names the D31 mechanism | **DONE** |
| 3 | **AMN latch → trade 20** | "verify at wave close; no action expected" | **CLEARED, and then some** — trade 20 journaled, filled, and CLOSED (stop-hit 2026-08-11) | **DONE** |
| 4 | **LQDA stray-order** | Phase-22-gated, persists by design | unchanged; LQDA has since FILLED | **no action** (Phase 22) |
| 5 | **trade-20 `entry_intent` NULL** | deliberate, Phase-22-gated | unchanged — **and now attached to a CLOSED trade with a realized result** | **no action** (Demand A) |
| 6 | **`invalid_ohlc` 52** | a watch, not clearable | watch | **no action** |

## FINDING 1 — RD's forward-test condition is SATISFIED, four times over

**This is the item the pass exists to surface.** RD ruled discrepancies 96/97/98 forward-test-conditional:
*"the next nightly reconciliation run DECIDES. No fifth emission → close all three `journal_corrected`,
each with a reason describing ITS OWN row. A fifth → they are LIVE and the fix did not take."*

**The emission chain, read off `reconciliation_discrepancies.run_id`:**

| run | emitted |
|---|---|
| 93 | disc 95 (FTRE `entry_price_mismatch`) |
| 94 | disc 96 |
| 95 | disc 97 |
| 96 | disc 98 |
| **97** | **— no FTRE emission** |
| 98 | disc 99 (`untracked_broker_position`, AMN — a different type) |
| **99** (2026-08-11) | **0 discrepancies, `state='completed'`** |
| **100** (2026-08-12 03:44) | **0 discrepancies, `state='completed'`** |

**There is no fifth FTRE emission across four subsequent completed runs, and the two most recent runs
emitted nothing at all. The D31 entry-side fix TOOK.**

**RD owns this watch and said he would post either way; the deciding event has now occurred four times
and he may not have looked since run 97.** The condition is his to declare satisfied — I am reporting
the evidence, not closing the rows. When he does, his own ruling requires **each row's reason to
describe ITS OWN row**: 97/98 are the *ambiguous-match* pair, NOT 95's zero-delta text.

## FINDING 2 — a standing unresolved warning the inventory could not have known about

**Discrepancy 99 — `untracked_broker_position`, AMN, `material_to_review=1`, `resolution='unresolved'`,
raised by run 98 on 2026-08-08:** *"AMN: +5.00 sh @ $+180.00 held at broker, not in journal."*

**It is STALE: the condition it describes has since cleared.** AMN was journaled as trade 20 and has
since closed; runs 99 and 100 emitted zero discrepancies, so the untracked-position check no longer
fires. The row nonetheless sits `unresolved` and material, describing a state of the world that ended
four days ago.

**It post-dates the 08-10 inventory, so it is not in §8.5's table** — which is precisely why the pass
had to re-derive rather than tick off a list. **Route: the resolve surface, with the resolution chosen
by whoever owns it** (its correct disposition is a judgment — `journal_corrected` understates it, since
nothing was corrected; the journal simply caught up). I have not chosen it.

Also noted, not actionable: **discrepancy 86** (`equity_delta`, `material_to_review=0`, 2026-07-11).
The delta has since moved from +$191.20 to −$410.13 across runs 98–100, which is the known
monthly-deposit drift class, not a defect.

## THE ONE OPERATOR ACTION — row 1, VSTS

**Everything else is either done, gated, or a director's call. This is the only row needing a human at
a surface**, and §8.5 binds how:

- **Decline VSTS through the 3a terminal** — per **R5, decisions are PER-LATCH and never retroactive**,
  and the decline's effective session is **server-computed** (flag B, live in item 4's write half). Do
  not hand-set a session.
- **Cancel the broker buy-stop**, and **log the cancel**.

Confirmation that it worked is mechanical: a `decline` row appears in `latch_order_intents` (there are
**zero** today, so the before-state is unambiguous).

**Per the operator's standing preference this is witnessed step by step, not handed over as a runbook.**

---

## What this pass changed in the repo

**Nothing but this file.** No discrepancy resolved, no latch written, no warning hand-cleared. That is
the correct outcome for a pass whose binding constraint is to route work to the surfaces that own it —
and the two findings above are worth more than any row I could have closed myself.
