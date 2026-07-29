# Commissioning Brief — 21-B: the prepared-order form (LOG-ONLY) + the execution-parity ledger

**From:** CHARC. **To:** the Phase-21 orchestrator. **Arc:** 21-B ([`phase21-scope-charc.md`](phase21-scope-charc.md)). **Committed:** 2026-07-28. Follows 21-A (merged + live, `1955aa59`, schema v32).
**§3 verdict: SCHEMA TRIPWIRE (the latch-action ledger + the telemetry surface column) → this brief embeds the CHARC architecture pass; conditions B1–B7 BINDING. NO L2 — nothing is sent to the broker in this arc.**

> **SCOPE SPLIT (CHARC, at commissioning).** The two joint false-all-clear priorities (RD's stale-close asymmetry + the run-level-stamp provenance gap) and the `data_asof_date` consumer survey are **carved OUT of 21-B into a sibling arc, 21-G** — different code loci (evaluator / shape-check vs web / ledger), different risk, different gate weight. **BUT THEY ARE COUPLED AND THE ORDER IS BINDING: 21-G MERGES BEFORE 21-B's ledger goes live.** Reason: the regime selection determines the recorded order TYPE (stop-limit vs limit), so a stale-price regime would write a WRONG TYPE into the execution-parity ledger — contaminating the metric with the framework's own defect and making a framework-vs-actual "mismatch" unattributable. Same ordering discipline as 20-A's Half-A-before-Half-B, and for the same reason: fix the writer before you trust what it writes.

## §0 References

- **The operator's design** (2026-07-27): the framework latches an A+ setup and presents a **filled form** — stop, limit, quantity — with **Place** and **Cancel** buttons; **before hooking anything up live, the buttons LOG the commands and we do post-facto verification.** RD adopted this over his own three-tier framing.
- **RD's measurement ruling** (operator-ratified): live-minus-shadow decomposes into MECHANICAL NOISE (removed by this design), DECISION VARIANCE (preserved — the discipline signal), FILL QUALITY (added later, going live). **The form makes a non-entry LEGIBLE** — today it is ambiguous between a decision and forgetting.
- **21-A shipped** the panel, the frozen-at-fire derivation, tier-1 order awareness, and the **view telemetry** this arc consumes (`latch_view_events`, migration 0032).
- Live subjects: FTRE (armed, GTC limit 18.89 resting, horizon 2026-08-31), VSTS (re-fired 07-27, pivot 16.90).

## §1 What 21-B ships

The **prepared-order form** on the latch panel — the framework's computed order presented for a one-action decision, with **buttons that LOG intent and make NO Schwab call** — plus the **execution-parity ledger** that makes the operator's response a first-class datum.

## §2 Requirements

### 2.1 The form — SHOW THE DERIVATION, not just four numbers (B1)
Stop / limit / qty **with their inputs visible**: pivot from which fire (run + date), cap as pivot×1.03, qty from which risk-policy line and which equity figure. **The D25 lesson applied:** a human gate only helps if the human can SEE that a computation is wrong; four bare numbers invite click-through. (D25 = the auto-corrector whose plausible-looking wrong values went unchallenged for six weeks.)

### 2.2 The THREE-STATE action space — BINDING, operator-ratified (B2)
**ACCEPT** (click place) · **DECLINE** (explicit, with reason — the highest-information datum) · **NO ACTION**. **No-action must NOT default to "away."** It is sub-split by the **objective view telemetry** 21-A already records:

| viewed | action | classification |
|---|---|---|
| NO | none | **AWAY / UNSEEN** → mechanical noise, **EXCLUDED** from the discipline signal, cost to the away bucket |
| YES | ACCEPT | accepted (decision datum) |
| YES | DECLINE + reason | declined (highest information) |
| YES | none | **AMBIGUOUS** → one attestation prompt at terminal; **if UNATTESTED the default is a DISCIPLINE LAPSE, not away** |

**The pessimistic default is load-bearing and must not be softened:** a permissive default silently flatters the measurement, and an honest instrument does not flatter its subject. **Never prompt where telemetry says never-viewed** — that cell is objectively resolved and an unnecessary prompt trains dismissal.

### 2.3 The execution-parity ledger — RD gates this shape (B3)
Per latch event record: **(1)** the framework's computed order + its derivation inputs (recomputable later); **(2)** the operator's actual action — clicked / declined+reason / acted manually — timestamped, with his actual params when he places his own; **(3)** the **per-field DELTA** framework-vs-actual (this IS the execution-parity metric); **(4)** outcome linkage — **store BOTH identities** (`evaluation_run_id`+ticker AND the detection identity), never a link to a prunable artifact (pure-recompute means the current artifact always holds the twin); **(5)** order-validity outcome. Read at the monthly cadence as: over N fires, the agreement rate, and where they differed, what it cost in R.

### 2.4 Telemetry surface column (B4)
Add the **surface** column RD ruled for, riding THIS arc's migration (CHARC deferred it off 0032 deliberately — it lands here with a real consumer). Record **(surface, latch_ids_rendered_with_actionable_detail, timestamp)**: the question is not "did he open the panel" but **"was THIS MANDATE visible to him during its armed window."** This keeps 21-F's surface architecture unconstrained.

### 2.5 The away-rate telemetry-health gate (B5, RD)
**The away rate must not be consumed without a telemetry-health check.** A silently broken beacon makes EVERY fire look like an away-fire — inflating the exact number that would justify stage-3 auto-place. The failure mode is not a wrong statistic; it is a wrong statistic pointed at the biggest pending decision.

### 2.6 Banked 21-A refinements to land here (B6)
The **separated-claims construction** — *"No alarms."* (unscoped; every latch IS alarm-checked) + *"Mandate-form check pending for N latches."* — replacing the scoped sentence, which rested on a misunderstanding and produces a vacuous zero-case in the 7-hour window. Plus the **pending-vs-permanent** wording distinction if 21-A's version needs refinement in light of it.

### 2.7 CHARC architecture conditions (B7)
- **Schema:** the ledger table + the surface column, **minimal**, `#11` one-commit multi-mirror discipline, strict backup-gate clause copied verbatim. v32→v33.
- **The four web hazards** (named at scoping, all still binding): **(a)** double-click/refresh → a per-latch **idempotency key**, not a disabled button; **(b)** GET/POST staleness → emit the computation as a **hidden anchor** and validate the POST against THAT anchor, never silently recompute at POST time; **(c)** cancel targeting → a specific broker order id, never by ticker; **(d)** framework-vs-operator order **distinguishability** in the recon path.
- **NO Schwab write call of any kind** — this arc logs intent only. The write path is 21-C, behind an operator-signed L2 endpoint diff.
- No new base-layout VM field; the panel's existing VM extends.

## §3 Tests + the acceptance test

> **CHARC CORRECTION 2026-07-28 — THE ACCEPTANCE TEST AS ORIGINALLY WRITTEN IS VACUOUS, AND THAT IS MY ERROR.** `latch_view_events` was created by migration 0032 **today**; FTRE fired **07-20**. So for 07-20→07-28 there is no telemetry and there never can be — `viewed=NO` is true of FTRE, but true of **every** latch, for a reason having nothing to do with operator behaviour. **The test would pass identically if the operator had stared at the panel all week.** It is also UNSTABLE: FTRE's armed window straddles the telemetry boundary, so a panel view tomorrow could flip its verdict about a vacation that already happened. I transcribed RD's proposed acceptance case into this brief as BINDING without checking whether the data could support it — the cite-without-verify class. **RESOLUTION (CHARC's own Phase-21 scoping fallback, applied):** `PRE_TELEMETRY` is a **distinct classification from AWAY** for any latch whose armed window began before telemetry existed, with the **partial-coverage** case handled explicitly. Both exclude FTRE's +1.22R from the discipline signal — but the REASONS differ, and this design rests on reasons being honest (*unclassifiable is LOST data, not uncertain data*). **For a test that actually discriminates**, use a seeded-telemetry fixture distinguishing viewed from never-viewed, or the first fully-telemetry-covered fire (VSTS re-fired 07-27 is also pre-telemetry by a day, so none exists yet — which argues for the fixture). RD rules the final form at plan-stage.

**FTRE ACCEPTANCE TEST (RD's, binding — READ THE CORRECTION ABOVE FIRST):** FTRE fired 07-20 during the operator's vacation → the panel shows **viewed=NO** across the armed window → it classifies **AWAY**, is **EXCLUDED** from the discipline signal, and its **+1.22R** lands in the away bucket rather than being scored against his judgment. *The scheme must reproduce this.*
Plus: each of the four classification cells; the attestation prompt fires ONLY on viewed=YES+no-action and never elsewhere; an unattested ambiguous cell defaults to LAPSE; a double-click yields ONE logged intent; a stale-anchor POST is REFUSED rather than silently recomputed; the ledger's per-field delta computes correctly against a real geometry (FTRE's actual GTC limit 18.89 vs the framework's computed order).

## §4 Gates

1. **RD plan-stage review** — the ledger shape + the stop/limit/qty derivation + the classification semantics (his named gates).
2. review-strong to convergence + **codex-auto-review (STANDING/required on production arcs, charter §2.9)** — and per the recipe, **verify the working invocation at dispatch; do not assume the last one still works.**
3. Suite + ruff + merged-head no-false-green.
4. **BINDING operator GUI witness, both states** + the merge/migration timing discipline (v32→v33 is again an exact-match guard: merge and live migration are ONE atomic operator-authorized step, held clear of the 17:30 window).
5. **Gate visibility (new, harness-architecture §2):** if the merge proceeds with a director gate outstanding, the merge report says so in one clause.
6. The ORCHESTRATOR posts the return to `charc,rd` after its QA.

## §5 Sizing + cells

Medium-large — the classification semantics carry the judgment; the form is conventional web. CHARC recommendation: **writing-plans `implementer-opus-xhigh`**, **executing `implementer-opus-high`**.
