# Wave item 4 — the executing delta: four director rulings that postdate the plan

**Read WITH** `docs/superpowers/plans/2026-08-07-phase21-item4-cancel-decoupling.md` (`4858abfe`). The plan converged at Codex R13 **before** these rulings existed. Where this delta and the plan disagree, **this delta wins** — it is the later document and it carries the rulings.

Nothing here re-opens the plan's design. Its four pieces, its one-arc judgment and its sequencing (piece 3 first and alone, then 4, then 1, then 2) all stand.

---

## D-1 — `cancel` does NOT inherit flag B (RD, ruling 1)

**Ruled:** a row's session field is server-computed at POST **wherever that field is consumed as a decision or ordering date**. Where it is pure provenance and something else carries the ordering, flag B does not reach it.

- `decline` meets the antecedent: `swing/latches/service.py:333` parses `action_session_date` into `_Terminal("declined", session)` — a **terminal date that orders the six-rung ladder**. A backdated decline can kill a latch before a re-fire that should have superseded it.
- `cancel` and `attest` do not: their session is provenance/display only (the repo contract states this explicitly — *"the time axis is `recorded_ts`, not `action_session_date`"*), and `candidate_id` carries mandate identity regardless.

**The one-arc judgment therefore STANDS and its reversal condition does not fire.**

### The obligation — a TEST, never a comment

Do **not** write a comment saying `cancel` will inherit flag B if a consumer appears. That is gotcha #31 exactly: a promise about a future arc, unenforceable by construction, that reads true forever after it goes false.

**Pin the caller-side obligation:** assert that the terminal-from-decisions path returns `None` for **every** non-`decline` intent kind — i.e. that no non-decline row's `action_session_date` can reach an ordering decision. Derive the kinds from `LATCH_INTENT_KINDS`, never a hand-written list, so a future kind joins the assertion automatically.

That test fails the day someone wires a cancel's session into an ordering consumer, which is precisely the day flag B must extend to it. **The test is the tripwire; a comment would only be a wish.**

---

## D-2 — the `operator_inferred` attribution defect (RD, ruling 2) — **MERGE-BLOCKING**

The plan (and my QA) framed this as "the docstring claims something the code cannot do." **RD verified both halves and the conclusion inverts: the docstring states the correct intent and `_inferred_origin` fails to deliver it.**

Trace a `cancel` row through `swing/cli_latches.py:138-147`:

- `validated_place_intent_id` is NULL by CHECK (`0033:576-577`) → the EXACT branch is unreachable.
- `actual_limit_price` / `actual_quantity` are NULL by the shape CHECK → every params comparison is `value == None` → the INFERRED branch is unreachable.
- It falls through to `any(p.candidate_id == …)` and returns **`operator_inferred`**.

**A framework-mandated order, cancelled through the framework, carrying the broker order id the framework itself recorded, is reported as OPERATOR-originated.** In a ledger whose entire purpose is framework-vs-operator attribution that is a *wrong answer*, not a missing one — and it is RD's own standing family violated: **alarm, never assert.** `operator_inferred` is a positive attribution asserted from an absence of evidence.

### D-2a — the correctness floor. **Lands with piece 1. Non-negotiable.**

A row whose kind **structurally cannot reach either attribution branch** is **UNDETERMINED** and must render as such — never as an operator attribution. Piece 1 multiplies the cancel population, which converts a dormant wrong answer into a systematically wrong column. RD is merge-blocking on this.

### D-2b — the EXACT chain. **DEFERRED to item 5. Do not build it here.**

The linkage RD derived is real and every hop is schema-guaranteed:

`cancel.actual_broker_order_id` → the `validity` row bearing that **same** broker order id → that row's `validated_place_intent_id` → the place.

`_inferred_origin` never attempts it because `place_intents` is the only lookup it is given. RD explicitly declined the scope call; **the orchestrator ruled it to item 5** (the D31 + A-4 entry-date arc — attribution and measurement, which is this fix's natural family), operator-concurred. Folding a new three-hop lookup into an arc already carrying four pieces manufactures the artifact-scale problem the plan just avoided.

**What is NOT available is shipping D-2b's absence as `operator_inferred`.** If D-2b waits, D-2a still lands.

### D-2c — the docstring

Correct it to describe what the code **does**, by **replacement, not annotation** (harness-architecture §5.1). Today it is a comment that reads true and is not.

---

## D-3 — legacy `decline` rows: ACCEPT, **provisionally** (RD, ruling 3)

RD queried the live DB on 2026-08-08: `latch_order_intents` is **empty — 0 rows of any kind**. There are no legacy declines, nothing for `service.py:333` to misread, nothing to migrate. The plan's migrate-nothing choice is correct.

**This is a ruling about a NUMBER, so it re-opens when the number moves.** It is ACCEPT *because and only because the population is empty*, not because legacy rows would be tolerable.

**Binding on you:** re-run that count **immediately before landing piece 2**, as part of the before-review suite —

```sql
SELECT intent_kind, COUNT(*) FROM latch_order_intents GROUP BY intent_kind;
```

If **any** `decline` row exists by then, **the ruling is void — STOP and route back to RD.** This is not hypothetical: the operator has an armed AMN latch and a live resting LQDA order.

Report the count you observed in your return report, whatever it is.

---

## D-4 — the `build.py` note is NOT yours (CHARC, ruling 4 — already shipped)

`swing/recommendations/build.py`'s false `__post_init__` guarantee was corrected **inline on main at `c46efcf4`**, before this dispatch, per the `b81da672` precedent. **It is not folded into this arc and you must not touch that file.**

One finding from it that **is** yours: the same false compound claim (`stop < pivot < zone_cap` presented as a `__post_init__` invariant) also sits at **`swing/latches/order_intent.py:375`**, which **is** in your scope and which the plan already corrects. `__post_init__` enforces the stop half only — `zone_cap` appears there solely inside the finiteness loop. Correct it by replacement, and do not restate the guarantee anywhere.

---

## Standing, unchanged by these rulings

- **Schema-stop on piece 2's read half: option (c)** — ship the write half, label the gap. Both directors concurred. **T7.8 stays unsatisfied BY DESIGN**, with the cost visible rather than silent. Do not attempt the template edit alone: it yields a control that renders and 400s, which is the 21-B defect this item exists to remove.
- No schema, no migration, no `swing/data` or `swing/trades` carve-out. If the work grows one, **STOP and route back** — that is a tripwire, not a judgment call.
- The Codex `fast` tier gap in the WSL config home was **fixed by CHARC**; `-p fast` now resolves. Your binding tier at execution is **`strong`** regardless.
