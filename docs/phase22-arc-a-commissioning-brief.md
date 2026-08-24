# 22-A — Entry-path order↔mandate binding (commissioning brief)

**Commissioned by CHARC 2026-08-24; Phase-22 scope operator-ratified as proposed same day**
([`phase22-scope-charc.md`](phase22-scope-charc.md) Tier 1). **The stop-the-bleeding arc:** two
empty-cohort-key rows minted in nine days (CADL, then OII) by the same root; every resting order
that outlives its screen appearance mints another until this lands.

## 1. THE ROOT, verified in code

`swing/trades/origin.py:52` — `derive_trade_origin` resolves provenance from
`_latest_complete_evaluation_run_id(conn)` (`:27`, used again via `entry.py:344-368`): **the
latest complete run, NOT the run the operator acted on.** A ticker that drops off the screen (or
drifts bucket) between recommendation and fill derives `manual_off_pipeline` + NULL keys even
when a broker-validated latch order for the mandate EXISTS in `latch_order_intents` — OII's two
rows (place intent 1 + validity intent 2, broker order `1007523377009`, `accepted_by_broker`)
were never consulted at entry. Gotcha #30's family one level up: a "latest" stamp standing in
for per-row provenance. **Verified: neither `trades` nor `fills` carries ANY order/latch link
column today** (`entry_intent` is the only intent-adjacent column).

## 2. WHAT 22-A SHIPS (three coupled pieces)

1. **Latch-on-acceptance durable link.** When a latch order is validated as accepted by the
   broker (the `validity` intent row), that acceptance creates a durable order↔mandate link the
   entry path can later consult — so a fill inherits provenance instead of guessing. Schema
   shape (link column on a new/existing table vs link table) is the PLAN's call; §3 pass rides
   it. The plan must also state what happens for NON-latched fills (RHI-class watch-pool
   entries): **their current derivation path stays byte-identical** — this arc narrows the
   guessing only where latch evidence exists.
2. **Entry-path fix.** `derive_trade_origin`/entry recording consults the link (fill matched to
   a broker-validated latch order → provenance from the FIRE candidate through the latch graph)
   before falling back to the current derivation. `swing/trades/` entry-path carve-out,
   spec-scoped here.
3. **Citation-graph extension to the Demand-C surface** (RD-ruled 2026-08-24): a fill matched to
   a broker-validated latch order may cite the FIRE candidate + the LATCH VALIDITY row — both
   contemporaneous, both audit-trail-verifiable (the two-tier admission shape). **The last-word
   guard's bucket-series path stays UNTOUCHED for unlatched trades** — its refusal of OII's
   `aplus` citation is CORRECT for what the guard is; the latch ladder is a different AUTHORITY
   the guard structurally cannot see (scope boundary, not defect — preserve this framing in
   code comments).

## 3. THE GOVERNING SEMANTICS (RD's bound, second clause — encode, do not re-derive)

> **A latch dies at its own INVALIDATION (rung 4) or above — never of bucket drift** (rung 5 =
> `criteria_lapsed`, REPORT-ONLY by RD's arming ruling). The discriminator is the latch's own
> FROZEN invalidation — a semantic line the fire itself declared — never the bucket series.

The discriminator compares against values the fire froze (`latch_order_intents` framework
columns + the frozen invalidation), so it is a pure comparison against existing columns — no
later judgment, no run-level stamp anywhere in the predicate (#30).

## 4. THE ACCEPTANCE TEST — fully specified by three live cases; RD holds the plan to it

**From the record alone**, the shipped mechanism must reproduce:
- **AMN (trade 20):** close breached the frozen invalidation before the fill → does **NOT**
  label from the fire (negative control).
- **OII (trade 25):** bucket drifted to `watch`, invalidation NEVER approached, fill exactly at
  the frozen pivot on the validated order → **DOES** label from the fire (drift-is-not-death).
- **VSTS:** never filled → **nothing** (no label, no row).
Plus: **RHI (trade 24) unchanged** — the unlatched watch-pool path byte-identical before/after.
These are fixtures built from the REAL rows (synthetic-vs-emitter drift is the standing family),
with expected values computed under BOTH pre- and post-fix paths.

## 5. EVIDENCE RULES CARRIED (each invisible from inside the arc)

Contemporaneity as a COMPARISON against the cited row's OWN session anchor (never
`data_asof_date` — the wrong anchor is monotonically more permissive, 138/138) · two-tier
admission with the tier recorded · the Demand-B guard (annotation/abandonment rows PERMANENTLY
INADMISSIBLE as citations) · D36 (immutability verified against the audit trail, never inferred
from writer-absence; a column-name grep cannot see the dynamic-SQL corrector) · D38's §3.0 rule
(no SQL predicate filters/orders/limits on an unconstrained TEXT timestamp — validate before the
predicate).

## 6. LIVE APPLICATION (post-merge, operator-witnessed, step-by-step)

Trade 25 (OII) corrected through the extended surface: labels from the fire (faithful derivation
from candidate 12284), keys populated, tier recorded. **Calendar: RD's monthly read #3 runs the
first trading week of September — land BEFORE it or AFTER it, never across it.** If trade 25
closes before 22-A lands, the read carries it as a NAMED pending-label row (RD's clause).
Trade 20 (AMN) is NOT corrected by this arc — its vocabulary is 22-B's (`unintended_execution`);
22-A's mechanism must merely REFUSE to label it from the fire (the negative control).

## 7. PROCESS

Envelope: `swing/trades/` (origin/entry paths + the Demand-C service extension), `swing/data/`
(schema per the plan's link-shape decision + repo), `swing/cli.py` if the correction surface
grows a flag. Declared accepted limitations WITH reasons in every review prompt, challenge
invited. A-loop per the recipe (ledger, two-token verdict, round-5 check-in); **B at the
ORCHESTRATOR's gate** under introduced-vs-banked. Plan routes to CHARC (§3: schema + carve-out)
and **RD (the acceptance test + the bound's encoding — his gate)** before executing. Plan on
`main` before its branch is deletable. Dispatch recommendation: **writing-plans at opus-xhigh**
(the link-shape decision and the guard-authority seam are design-dense); **executing at
implementer-opus-high**.
