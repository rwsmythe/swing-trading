# Plan delta — Phase-21 boundary paydown **item 3a: the `declined` clear reason**

**Status:** the executing delta against [`2026-08-06-phase21-item3-criteria-lapsed.md`](2026-08-06-phase21-item3-criteria-lapsed.md) (branch `criteria-lapsed-plan`; NOT on `main`). CHARC ruled the SPLIT on `20260806T222427Z`: **3a is the `declined` path — armed, operator-facing — and it goes first; 3b is the dormant lapse machinery.** This document records only what changes for 3a. **Where the item-3 plan and a RULING disagree, the ruling governs.**

**Base:** `main` @ `c38b8537`. **Worktree:** `.worktrees/declined-clear-reason`.
**Inherited bindings (CHARC, verbatim):** 3a inherits **R5, R6 and the full six-rung ladder** — they are lifecycle rulings and the fold change lands with `declined`.

---

## §1 What 3a ships, and what it explicitly does not

| Item-3 plan task | 3a | Note |
|---|---|---|
| Task 1 — the vocabulary + every Python mirror | **YES, reduced** | `LATCH_CLEAR_REASONS` **4 → 5**, not 4 → 6. `criteria_lapsed` is 3b's. |
| Task 5a — the `declined` terminal | **YES** | Split into 5a.1 (the shared admissibility filter) and 5a.2 (the terminal + reader), because 5a.1 is green and safe at its own boundary while 5a.2 needs it to exist. |
| Tasks 2, 3, 4, 5b, 5c, 6, 7 | **NO** | The structural gate, the four calibrations, the per-session verdicts, the streak, the conjuncts, the countdown, the UNVERIFIABLE render, the arm flag, `framework_withdrawn`. All 3b. |

**Not built, and deliberately:** the streak, both conjuncts, the countdown, the UNVERIFIABLE render, `criteria_lapse_armed`, the lapse disposition. Nothing in the `declined` path needed them — the split seam held.

**Persistence: NONE.** Re-verified on this base. `clear_reason` appears in zero migrations; `decline` is already in `LATCH_INTENT_KINDS` and in the `0033:346` CHECK; `declined` is already in `LATCH_DISPOSITIONS`/`DECISION_DISPOSITIONS` and already emitted at `classification.py`'s rung 1-2. The arc reads `latch_order_intents` through the existing `list_intents_for_latch` and writes nothing. **Tripwire CLOSED, as CHARC ruled it.**

---

## §2 THE LADDER — the posed question, and the choice

The orchestrator posed it rather than deciding it: 3a ships `declined` but not `criteria_lapsed`, so does the rank table carry a rung for a reason that does not exist yet, or order only what exists? RD then sent a **LEAN, explicitly not a ruling** (`20260806T231336Z`), for ordering only what exists with a projection pin, and said the full table with a provable-unreachability pin would also be acceptable at his review.

### CHOSEN: order only what exists.

```python
_CLEAR_REASON_RANK = {"fill": 0, "declined": 1, "superseded": 2,
                      "invalidation": 3, "horizon": 4}
```

The reasoning, which was reached before RD's lean arrived and which his argument then reinforced:

1. **A rank table is a MIRROR of the clear-reason vocabulary in the §4.1 sense** — it enumerates the vocabulary and assigns each member a property. In 3a that vocabulary gains `declined` only. A rank entry for `criteria_lapsed` would be a mirror carrying a value `LATCH_CLEAR_REASONS` does not contain, which is the inconsistent-vocabulary state gotcha #11 exists to forbid, arriving from the other direction.

2. **The rung would not merely be unreachable — it would be UNCONSTRUCTABLE.** `Latch.__post_init__` rejects a `clear_reason` outside `LATCH_CLEAR_REASONS`, so no `criteria_lapsed` terminal can be built at all in 3a. The rung is not dormant code awaiting a caller; it is a key that nothing in the process can look up.

3. **The unreachability test that would justify it cannot fail.** A test asserting "no fixture produces `criteria_lapsed`" passes against every implementation, including one that never had the rung. That is the vacuous-negative class RD owned in his own arm-flag note two days ago — a negative assertion that holds regardless of the code under test. Buying a rung with a test that cannot discriminate is a net loss.

4. **The insertion cost is one dict entry, and it belongs beside the test that discriminates it.** 3b adds `criteria_lapsed` to `LATCH_CLEAR_REASONS` in its own #11 commit; the rank goes in the same commit, next to the neighbouring-rung tie tests. Deciding the rank in an arc that cannot exercise it moves the decision away from its evidence.

**RD's lean adds the sharper framing and it is adopted:** a rung for a reason with no producer is *a vocabulary member waiting for its writer* — the guard-preceding-its-condition class he has now ruled against twice. The six-rung ladder's AUTHORITY lives in the R6 ruling, not in a preview rung.

### The projection pin (RD's own shape, adopted as specified)

Two tests, in `tests/latches/test_declined_terminal.py`:

* **domain** — `set(_CLEAR_REASON_RANK) == set(LATCH_CLEAR_REASONS)`. Asserting the DOMAIN rather than a subset is what makes it survive 3b: the moment a reason joins the vocabulary without a rank, this fails. The vocabulary and its precedence cannot drift.
* **order** — the rank-sorted keys equal `["fill", "declined", "superseded", "invalidation", "horizon"]`, R6's ladder with the producerless reason left out; plus ranks distinct, because a duplicate makes the tiebreak depend on the order the candidate list happened to be built in.

3b re-asserts the same two properties over six members. One authority, two projections, each exact over its own vocabulary.

### Going past "unreachable": every rank is EXERCISED

The dead-code objection is answered in the strongest available form — not "provably unreachable" but **provably exercised**. The resolver was restructured so all five ranks are load-bearing:

| Rank | Where it decides something |
|---|---|
| `fill` 0 | the fill rung is now `fill.order_key <= nonfill.order_key`; rank 0 is what makes a fill dated ON the winning terminal take it |
| `declined` 1 | same-session decline vs invalidation; and vs `superseded` in the fold |
| `superseded` 2 | the fold's R6 comparison — `min` over `(declined, superseded)` |
| `invalidation` 3 | same-session invalidation vs horizon |
| `horizon` 4 | the horizon is now a ranked CANDIDATE, not a fallback |

**Each restructure is behaviour-identical to the shipped control flow.** Both walks are capped at `horizon_expiry`, so any date they produce is at-or-before it and a boundary-session collision falls to rank; `fill` rank 0 is strictly below every other rank, so `fill.order_key <= nonfill.order_key` reduces exactly to the shipped `entry.entry_date <= nonfill.session`. The whole existing terminal suite passes unchanged, and a null-case test asserts the derivation with no decisions equals the shipped one latch-for-latch.

---

## §3 The mirror inventory (gotcha #11), 4 → 5 in ONE commit

Produced by grepping the member VALUES across `swing/`, `tests/`, `scripts/`, `research/` — a grep on the CONSTANT NAME returns only `constants.py` and `models.py` and misses both design mirrors.

| # | Site | Edit |
|---|---|---|
| 1 | `swing/latches/constants.py` `LATCH_CLEAR_REASONS` | **+`declined`** (canonical) |
| 2 | `swing/latches/models.py:173` | none — imports #1 |
| 3 | `swing/latches/service.py` `_STATE_BY_CLEAR_REASON` | **+`declined` -> `horizon_expired`** (design mirror; OQ-2 Option B applied per R1) |
| 4 | `swing/latches/orders.py:56` `_CRITICAL_STALE_CLEAR_REASONS` | **+`declined`** (design mirror; OQ-1's duty reasoning per R2) |
| 5 | `swing/latches/classification.py` `clear_reason == "fill"` | none — single-value equality; a decline is not a fill |
| 6 | `swing/web/view_models/latches.py` `_state_label` | **+ a `DECLINED - operator declined on <session>` reason branch, BEFORE the state map** |
| 7 | `swing/web/view_models/latches.py` `_TERMINAL_STATE_LABELS` | none — #6 pre-empts it, as it does for `superseded` |
| 8 | `swing/web/templates/latches.html.j2:54-57` | none — renders `row.clear_reason` verbatim |
| 9 | `tests/latches/test_identity.py` `test_locked_constants` | **updated to five** |
| 10 | `tests/latches/test_close_provenance.py:28` | none — **inspected**: a docstring mention of the `LATCH_STATES` precedent, not a mirror |
| 11 | `docs/rd-state.md:50` | **none needed** — already carries R6's full ladder as a RULING (not a code mirror), and reads true |
| 12 | `swing/latches/service.py` `_resolve_terminal` docstring | **corrected here** — 5a.2 is the task that falsifies it |
| 13 | `swing/latches/service.py` `derive_latches` clause (ii)(b) prose | **corrected here** — R6 makes `superseded` conditional |

Sites 2, 5, 7, 8, 10 and 11 are listed **because they need no edit**: an inventory recording only what changed cannot be checked by the next reader.

**New in 3a and NOT a clear-reason mirror:** `_CLEAR_REASON_RANK` (§2) is a mirror of the same vocabulary on a different axis, pinned by domain equality rather than enumerated by hand in a second place.

---

## §4 Residuals — what 3a APPLIED as an inference, flagged for RD

| | Applied as | Pinned by |
|---|---|---|
| **R1** `declined` -> `horizon_expired` | OQ-2's Option B principle extended to this reason | an exact-literal test; **one map entry to change** if he rules otherwise |
| **R2** `declined` is critical-stale | OQ-1's duty-not-fault reasoning, which reaches here identically | a literal set + a behavioural test on two latches identical except `clear_reason`; **one frozenset member to change** |
| **R5** a successor's decision never amends its predecessor | **RULED by RD** — needs no mechanism: candidate-FAMILY keying gives it | `test_a_successor_latchs_PLACE_never_resurrects_its_predecessor` |
| **R6** `declined` beats `superseded` | **RULED by RD** — the fold consults the decline before it stamps | `test_declined_BEATS_superseded_...`, which also asserts the successor still arms |

`superseded > invalidation`, the other half of R6, **was already true and needed no change**: the liveness probe's bar bound excludes the re-fire session, so a same-session invalidation cannot compete with the supersede, while an earlier one sends the fold to clause (iii) and wins on date. Verified against `tests/latches/test_service_terminal.py:469-470`, not assumed.

---

## §5 Deviations from the item-3 plan

* **`_close`'s `superseded_session` parameter became `forced`.** Two mutually exclusive optional arguments (a session and a terminal) is a worse seam than one: R6's branch passes the WINNER of `declined` vs `superseded` through a single stamping path, which is what makes the ranked comparison the only rule.
* **`decision_bounds_for` is a named helper** returning `(lower, upper, decline_upper)`, not a bound each caller derives. The panel and the monthly report both call it — the D6 two-implementations-of-one-rule class this phase has spent itself closing. The bound is **per kind**: PLACES reach through the nominal window (matching the lifecycle, so a late-arriving terminal cannot erase a placement already logged), DECLINES are capped at the actual terminal (a decision recorded after the mandate ended cannot be about it).
* **A defect the bounding introduces, found and fixed.** `resolve_execution_outcome_for`'s FORWARD guard recomputed "is this the LATEST place?" over the FULL intent set; once the place is selected from the ADMISSIBLE view, a place latest-in-view but not latest-in-raw fails that guard and loses its own fill's vouching. Fixed with a `place_view` keyword scoping the GUARD only; validity children still come from the full set.

## §6 THE ONE REVERSAL — a recording-surface widening that was built, then removed

**An earlier cut of this arc widened `rederive_prepared_order` so a `declined` latch stayed amendable.** The motivation was real: a decline now terminates, so the operator could end a mandate and never take it back, which sits badly beside `build_idempotency_key`'s `prior_intent_id` (present so a CORRECTION keys differently from a REPLAY) and beside `governing_decision` resolving the family by RECENCY.

**It was REVERTED, and the reason is structural rather than a detail.** `build_latch_panel_vm` builds prepared-order blocks from LIVE latches alone, so a declined card renders **no decision form at all**. Widening only the POST-time re-derivation therefore created a path reachable **only by replaying a form rendered before the decline** — a stale-form hole, not a corrective path. And a decline can MASK a later fill or invalidation under earliest-date-wins, so erasing it with a late `place` lets the masked terminal become authoritative and persists a placement against a mandate already filled or dead.

**The affordance is a RENDER-plus-ROUTE change and belongs with wave item 4**, which already owns the ruled principle: *recording an operator action and alarming on a detected problem are different functions; the affordance to record must not be gated on the alarm that detects.* Building half of it here bought a hole instead of a path.

**The cost is PINNED, not papered over:** `test_a_DECLINED_latch_REFUSES_a_further_decision_and_that_cost_is_pinned` (route) and `test_a_TERMINATED_latch_is_closed_to_the_recording_surface` (re-derivation) both assert the refusal and name what flips when the affordance ships.

## §7 Flagged, not fixed — the residual cluster

Each is recorded in the code where it lives, with its trigger and its named fix.

| # | What | Why not here |
|---|---|---|
| **A** | **The correction affordance** — a declined latch cannot be amended through any surface | render + route; wave item 4 owns the ruled principle |
| **B** | **A one-session-stale form can backdate a decline** over a later real terminal, orphaning a fill (the route's grace is `sessions_behind > 1`) | a DECISION-SEMANTICS question: `action_session_date` says which mandate a decision is ABOUT, `recorded_ts` when it was made. Choosing between them, or dropping the grace for decision kinds, moves shipped semantics — RD's to rule |
| **C** | **`superseded > horizon` is not implemented** on the expiry-session tie (branch (b) is never reached) | **PRE-EXISTING** — the `live_probe is None` selector has no changed lines in this arc. Fixing it moves a shipped terminal AND an alarm severity |
| **D** | **The derivation reads decisions globally; the classifiers re-read per latch** — a persistently malformed row for one candidate can leave another latch armed-but-classified-declined | corrupt-ledger-only (a row failing the validator it was written through). Fix = single-source the decision evidence through `LatchDerivation`, restructuring its contract |
| **E** | **`swing/cli_latches.py`'s `current_cycle_place` for DISPLACED cycles** and **`classify_latch` retaining `governing_place_intent_id` when a decline governs** | **PRE-EXISTING**, verified on `main`: it already used `governing_intent(intents, "place")` while the CLI already used `current_cycle_place`. This arc aligned the POPULATION, never the rule |

## §8 The two named cross-arc couplings (restated per CHARC)

* **Item 4** edits `swing/latches/orders.py` — the same file as OQ-1's `_CRITICAL_STALE_CLEAR_REASONS`, which 3a widens. Different line, same file twice. **And item 4 now also inherits residual A**, the correction affordance.
* **Item 5** moves trade 19's `entry_date` 07-23 -> 07-31, which moves item 3's FTRE acceptance fixture. **3a does not use that fixture** — its cases are the VSTS geometry plus synthetic FTRE latches whose dates the tests own — so the coupling does not bite here. It still binds 3b.

Serial ordering covers both; the integration step is where they get CHECKED.
