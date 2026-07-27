# Commissioning Brief — 21-A: the latch panel + order-state awareness + view telemetry

**From:** CHARC. **To:** the Phase-21 orchestrator. **Arc:** 21-A ([`phase21-scope-charc.md`](phase21-scope-charc.md), the opener). **Committed:** 2026-07-27, operator-approved scope. **Parallel with 21-D** (file-disjoint).
**§3 verdict: SCHEMA TRIPWIRE (the view-telemetry record) → this brief embeds the CHARC architecture pass; conditions A1–A6 BINDING.** NO L2 (the Schwab order READ endpoints are already in the locked set). NO `swing/trades` carve-out expected — the derivation is read-only.

## §0 References (verified on disk 2026-07-27 unless noted)

- **The settled latch semantics** (operator-adopted 07-23, RD charter §7): an A+ fire LATCHES an entry mandate — GTC at the fire's pivot, buy-zone limit cap at **pivot ×1.03**; clears ONLY on **(a) FILL**, **(b) SETUP INVALIDATION** (close below the fire-time initial-stop / base break), **(c) HORIZON** (~20 sessions, the shadow-parity bound). **Bucket-label flicker NEVER clears it.**
- **RD's six derivation constraints** + the three-state action requirement (operator-ratified) — §2.3/§2.4 below.
- **Data facts (CHARC-verified):** the A+ fires ARE `candidates` rows with `bucket='aplus'`, keyed `(evaluation_run_id, ticker)`, each carrying **`pivot` + `initial_stop` frozen at that run** (126 distinct runs retained). Live proof: FTRE @ run 121 = **18.34 / 14.88** (fire-time) while later rows drift to 15.19/15.25/16.51 and the pivot walks to 20.19; VSTS @ run 99 = 13.56/11.62 and @ run 126 = 16.90/13.40 — **separate rows, so per-fire identity is structural.** **`pattern_detection_events` carries NO pivot/stop** — do NOT key the price derivation on it (RD's demand statement said otherwise; corrected).
- **Order-read plumbing (exists, in production):** `get_account_orders` / `get_account_orders_audited` (`swing/integrations/schwab/trader.py:329/379`), `map_orders_to_fill_candidates` (`mappers.py:241`), the `_step_schwab_orders` pipeline step — currently consumed for fill reconciliation.
- **The FTRE case** (the arc's reason to exist): fired 07-20 during the operator's vacation; a one-cent miss through 07-21; 07-22 crossed with the order dead; **+1.22R shadow-vs-live, RD-quantified.**

## §1 What 21-A ships

1. **The latch panel (read-only):** per live latch — fire date, **latched (frozen) pivot**, zone cap, current price vs zone, **sessions-to-horizon**, **invalidation level (frozen)**, and latch state (`armed` / `order_resting` / `filled` / `invalidated` / `horizon_expired`). **Invalidation visibility is FIRST-CLASS** — a fired invalidation must be loud, because the operator's one manual duty is the invalidation-cancel of a resting order.
2. **Tier-1 order-state awareness:** join live open broker orders to armed latches and surface, per latch, whether an order is present, its stop/limit/qty, and **whether those AGREE with the latched pivot + zone cap**. Two alarms are the point: **LATCH ARMED + NO RESTING ORDER** (the FTRE failure mode) and **ORDER RESTING + LATCH CLEARED** (the stale-order hazard).
3. **View telemetry (RD-ruled folded in):** record that the latch surface was **viewed while a latch was armed** — a timestamp, objective, no self-report. This is what lets 21-B distinguish *away* from *saw-it-and-didn't-act*; without it the fires between 21-A and 21-B are **permanently unclassifiable**.

## §2 Requirements

### 2.1 Derivation (RD gates this section)
- Latch identity = **the fire**: `(evaluation_run_id, ticker)` — **plus the detection identity `(ticker, detection_date)` stored explicitly** (RD's finding-4 refinement: the shadow artifact keys on a DIFFERENT id space; storing only the evaluation identity makes the shadow join derivable-by-convention rather than exact — *cheap now, unrecoverable later*).
- All prices come from **the fire's own `candidates` row**. Never a later row.

### 2.2 Schema (the tripwire — CHARC conditions)
- **A1 — MINIMAL, but not corner-painting.** Propose the smallest table that serves the telemetry record, **and state explicitly how it extends to 21-B's known ledger requirements** (computed order + derivation inputs, the three-state action + reason, the per-field framework-vs-actual delta, attestation, order-validity outcome). If the honest answer is that ONE table serves both, propose that — do not design 21-B's columns speculatively, but do not force 21-B into an immediate rework either.
- **A2 — the #11 one-commit multi-mirror discipline** (migration CHECK + Python constants + dataclass validator + any repo guard land in ONE task). Migration `0032`+ per the numbering; the backup-gate STRICT `pre_version == target-1` clause shape is copied verbatim.
- **A3 — the 0032 taxonomy-type rider is a SEPARATE migration** (CHARC ruling): do NOT merge unrelated schema into this arc's migration.

### 2.3 The six derivation constraints (RD, BINDING verbatim)
1. **FREEZE AT FIRE TIME** — latched pivot, stop basis, zone-cap percent are the values AS OF THE FIRE, never the current candidate row. *(Live trap, and it has already bitten its author: RD quoted FTRE's invalidation as 16.51 — a drifted value — when the fire-time level is 14.88, ~11% early.)*
2. **HORIZON IN SESSIONS, NOT CALENDAR DAYS** (the 19-E ruling-A precedent, where exactly this was fire-vs-no-fire on AMN).
3. **PER-FIRE IDENTITY** — keyed to the fire, not the ticker; concurrent/sequential latches on one ticker must never merge or overwrite (VSTS has fired twice).
4. **FILL DETECTION IS LATCH-SPECIFIC** — a pre-existing position or unrelated order in the same ticker must not read as this latch's fill.
5. **CLEAR-REASON RECORDED, NOT INFERRED** — fill / invalidation / horizon are distinct terminal states, each stamped with which cleared it and when; the panel's history is the audit trail.
6. **INVALIDATION EVALUATED ON CLOSES**, not intraday touches (consistent with the exit-side doctrine + the engine's `ma_close_below` semantics).

### 2.4 Telemetry scope discipline (RD)
**One view-timestamp record.** The attestation prompt and the three-state action capture are **21-B's**, not this arc's. "The measurement value is in the classification being HONEST, not in elaborate instrumentation." Do not build the prompt here.

### 2.5 Web-layer conditions (CHARC)
- **A4 — the view record is a WRITE, and our GET path does not write.** Design the seam deliberately (a beacon POST or an explicit view-log write); do NOT make a plain page GET mutate state as a side effect. State the chosen seam in the plan.
- **A5 — no new base-layout VM field** (the every-base-VM-or-500 gotcha); the panel is its own VM/route.
- **A6 — read-only derivation, defensive:** absent orders / absent prices / a malformed row degrade gracefully to a visibly-degraded panel, never a 500 (the 20-C malformed-envelope precedent — verify whether any write path prevents the bad shape BEFORE dismissing it as impossible).

## §3 Tests

Fixtures from the REAL live geometries (`feedback_adversarial_review_verify_data_shapes`): **FTRE run 121** (fire 18.34/14.88 with later drifted rows present — the discriminating fixture: a panel reading the latest row shows 16.51 and FAILS), **VSTS runs 99 + 126** (two latches, one ticker — must not merge), **AMN** (the sessions-vs-calendar discriminator: a calendar-day horizon computes a different expiry than a sessions horizon — build it so the wrong basis fails). Plus: armed-with-no-order fires the alarm; order-resting-with-latch-cleared fires the inverse; invalidation evaluates on a CLOSE below (an intraday touch that closes above must NOT invalidate); each terminal state stamps its own clear-reason; the view record writes once per view and is attributable to the armed latch.

## §4 Gates

1. **RD plan-stage review — the derivation rules** (his named gate: shadow-window parity + the six constraints + both identities).
2. review-strong to convergence + codex-auto-review (production web + schema).
3. Suite + ruff + merged-head no-false-green.
4. **Operator GUI witness, BOTH states** (the seeded-gate memory): a lit panel with a live/seeded armed latch (FTRE and VSTS are live subjects) **and** the clean/empty state. Browser, not TestClient.
5. The ORCHESTRATOR posts the return to `charc,rd` after its QA.

## §5 Sizing + cells

Medium — the derivation carries the judgment, the panel is conventional web. CHARC recommendation: **writing-plans `implementer-opus-xhigh`** (derivation + the schema shape that must not corner 21-B), **executing `implementer-opus-high`**. Orchestrator selects + announces.
