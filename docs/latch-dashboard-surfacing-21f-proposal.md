# Proposal — 21-F: surface latches on the dashboard (operator-originated)

**From:** the orchestrator, relaying an operator demand raised 2026-07-28 at the 21-A GUI witness.
**To:** CHARC (scope + surface architecture) and RD (measurement integrity — there is a real collision, §4).
**Status:** PROPOSAL. Not scoped, not commissioned. The orchestrator does not own scope; this is the demand plus the engineering context needed to rule on it.
**Baseline:** main `57e4e797` (21-D merged); 21-A witness-PASSED, pending merge.

---

## 1. The demand, in the operator's own framing

At the 21-A witness the operator passed both states, then asked whether the arc planned to make the data
easier to consume — specifically:

1. **An open-latches summary table on the dashboard**, and
2. **Open orders with no valid latch promoted into the dashboard alert messages.**

His argument, which is the strongest part of this proposal and is his rather than mine:

> the panel should come to me, not me to it

## 2. Why this is not a nicety

The arc's founding failure was **FTRE**: a latch armed 2026-07-20, the operator on vacation, the order dead
by 07-22 when price crossed — RD-quantified at **+1.22R shadow-vs-live**. That was an **attention** failure,
not a knowledge failure.

A surface the operator must *remember to navigate to* is still attention-dependent. The phase theme is
"take memory and arithmetic out of the entry loop"; a standalone route addresses the arithmetic and leaves
part of the memory problem standing. The dashboard is the surface actually opened daily.

The empty-state witness made this concrete: on a substrate with no live latches, the panel correctly
surfaced resting orders with no mandate as items needing correction — the stale-order hazard RD named on
07-23 as the inverse of armed-with-no-order. That alarm is most valuable exactly when the operator is *not*
thinking about latches, which is precisely when he will not open `/latches`.

## 3. What exists after 21-A, and what does not

**Exists:** the full derivation (frozen pivot/stop, sessions-horizon, the two-branch fire identity, terminal
states with recorded clear reasons), the two alarms, order-state awareness with the RD two-form mandate
shape check, and the view-telemetry record. `GET /latches` plus a topbar link.

**Does not exist, and is not banked anywhere:** any dashboard surfacing. The orchestrator checked the plan's
§H banked list and the whole plan — the word "dashboard" appears twice, both incidental. This is a genuine
gap, not a deferred item.

**The mechanism it would extend already exists** (premise checked per discipline #38): `DashboardVM` already
carries `stale_banner`, the unresolved-material-discrepancy banner and `banner_resolve_link`, plus the
`needs_review_badge` partial. A latch alarm joins an established banner family rather than inventing one.
That makes this cheaper than a new surface — mostly view-layer work over a derivation that now exists.

## 4. THE COLLISION — RD's lane, and it must be ruled before this is built

**A naive dashboard summary would corrupt the 21-B away-rate.**

RD's telemetry design records *whether the latch surface was viewed while a latch was armed*, which is what
lets 21-B distinguish **away** from **saw-it-and-chose-not-to-act**. His binding ruling: no-action must not
default to away, and an unattested ambiguous cell defaults to **discipline lapse** — deliberately
pessimistic, because an honest instrument does not flatter its subject.

If latch state renders on the dashboard, the operator can see everything he needs **without ever hitting
`/latches`**. Telemetry then records never-viewed, the fire classifies as **away**, and the away rate
inflates — biased **optimistic**, the exact direction RD forbade.

This is not a rounding error. RD named the away rate as *the quantified business case that will justify or
kill stage-3 auto-place*. A biased-optimistic away rate biases the decision **toward automating the
operator's entries**. The 21-A plan already banked the mirror-image hazard (§H.1b: a silently broken beacon
makes every fire look like an away-fire) and required 21-B to gate any away-rate read on telemetry health.
A dashboard surface is a second, independent path to the same corruption — and unlike the broken beacon, it
would be working exactly as designed.

**Resolution candidates (RD's choice, not the orchestrator's):**

- **(a) The dashboard surface emits its own view record.** Simplest; treats "saw it on the dashboard" as a
  view. Requires deciding whether a passive glance at a summary tile is evidentially equal to opening the
  panel — arguably it is, since the mandate and its alarms are both visible.
- **(b) Telemetry keys on "latch state was rendered anywhere"** rather than on the panel route, with the
  surface recorded alongside the timestamp. Preserves the ability to analyse the two surfaces separately.
- **(c) The dashboard shows only an ALARM COUNT / link, never the mandate detail** — deliberately
  insufficient to act on, so acting still requires opening the panel and generating a genuine view record.
  Preserves the measurement exactly; costs some of the operator's convenience.
- **(d) Accept the bias and state it.** Named for completeness. Contradicts RD's do-not-flatter rule and is
  not recommended.

Note that (c) is in direct tension with the operator's stated need. That tension is the actual decision.

## 5. Sequencing recommendation

**With or after 21-B, not before.** 21-B is where the three-state action capture, the attestation prompt and
the away-rate consumption land. Settling the telemetry contract there and building the dashboard surface
against it is strictly cheaper than shipping a surface now and retrofitting the measurement.

If the operator wants relief sooner, option (c) — an alarm count plus a link, no mandate detail — is the one
variant that is measurement-safe today and could ride alongside 21-A's merge as a small rider.

## 6. Open questions

**For CHARC (scope + surface architecture):**
- Is this a new arc (21-F), a rider on 21-B, or deferred to a later phase?
- `DashboardVM` gains fields — a per-VM field, NOT a base-layout field, so the every-base-VM-or-500 gotcha
  does not fire; confirm that read of A5's boundary.
- Does the latch alarm join the existing banner family, or does the growing banner set need consolidation
  first? (Register item **D15**, base-VM consolidation, is adjacent.)
- The dashboard is a hot path; the panel's order read is a live Schwab call. A dashboard surface must NOT
  inherit a per-page-load broker call — 21-A §H.4 already banked "no order-fetch cache" as a V2 candidate,
  and this proposal likely forces that question.

**For RD (measurement integrity):**
- Which resolution in §4, and does it change what the telemetry record must store?
- Does a dashboard glance count evidentially as a "view" for the away/lapse classification?
- Should the two surfaces be distinguishable in the ledger?

## 7. What the orchestrator is NOT proposing

No position on scope, no position on the §4 resolution, and no design of the telemetry change. The demand is
the operator's, the surface-architecture call is CHARC's, and the measurement call is RD's. This document
exists so both rule on the same facts.
