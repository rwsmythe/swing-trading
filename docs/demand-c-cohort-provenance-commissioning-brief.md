# DEMAND C — Cohort-key provenance-correction surface (commissioning brief)

**Commissioned by CHARC 2026-08-12; operator concurred with dispatch same day.** Origin: RD's
operator-authorized Demand C (2026-08-12 14:49Z), his adoption of the contemporaneity comparison
(16:40Z), and the D36 correction (immutability is verified against the audit trail, never inferred
from writer-absence). **Deadline: shipped and applied to the live case BEFORE monthly read #3
(first trading week of September 2026).**

## 1. THE DEMAND

An **audited correction surface for the COHORT KEYS** — `hypothesis_label`, `candidate_id`,
`trade_origin` — which today have **no UPDATE path anywhere in `swing/`** except the generic
PRAGMA-allowlist corrector, which requires a discrepancy, and nothing here disagrees between
broker and journal. **Minting a synthetic discrepancy is REFUSED** (the item-5 precedent).

Shape: item 5's `correct-entry-date` generalized — CLI surface, single-transaction service
(`BEGIN IMMEDIATE`, reject caller-held tx, the `entry_date_correction.py` idioms), audited,
server-derived targets. **Read `swing/trades/entry_date_correction.py` before planning; it is the
house pattern for exactly this.**

## 2. THE BINDING CONSTRAINT — the evidence rule (RD's, operator-authorized)

> A cohort assignment may be corrected ONLY to what the framework's OWN CONTEMPORANEOUS RECORD
> says — never to what anyone later judges it should have been. The correction cites the record
> it corrects TO.

Three structural consequences, none optional:

1. **The citation is STRUCTURAL, never free-typed.** The correction names the `candidates` row
   and the `daily_recommendations` row it derives from and **refuses without them**. A surface
   that lets an operator type a hypothesis label lets a future operator curate H1 (which stands
   at 2/20 — post-hoc assignment on judgment is the cheapest way to flatter it and would be
   indistinguishable from diligence).
2. **Target values are DERIVED, never composed.** `hypothesis_label` is READ OFF the existing
   cohort rows (trades 17/18 carry `'A+ baseline (aplus)'`); `candidate_id` comes from the cited
   row itself; `trade_origin`'s target is read off the same cohort rows (`'pipeline_aplus'`).
   The operator picks the CITATION; the surface computes every written value from it.
3. **CONTEMPORANEOUS IS A COMPARISON THE CODE PERFORMS** (RD-adopted): the surface **REFUSES a
   citation whose record does not PRE-DATE the fill.** The anchor is **the CITED ROW'S OWN
   session anchor** — `candidates` reached through `evaluation_run_id` →
   `evaluation_runs.action_session_date`, and `daily_recommendations.action_session_date` on its
   own row — **NEVER `evaluation_runs.data_asof_date`**, which is a cohort MAX (gotcha #30) and
   would bless a lagging row as fresher than it is. **The wrong anchor passes every test built
   from the right example** (CADL's rows are genuinely contemporaneous), so the discriminating
   test in §6 is mandatory, not advisory.

## 3. THE AUDIT SHAPE — a fork the plan must resolve, with CHARC's leaning stated

**Verified on the live DB: `reconciliation_corrections.discrepancy_id` is `NOT NULL` with an FK
to `reconciliation_discrepancies`.** So the existing audit table does NOT suffice without change,
and RD's "no schema change if the existing audit table suffices" has a false antecedent. Two
honest options:

- **(i) Rebuild `reconciliation_corrections` to make `discrepancy_id` nullable.** Rejected-by-
  leaning: it rebuilds an APPEND-ONLY audit table to WEAKEN a guarantee, and every existing row's
  semantics (discrepancy-anchored) would share a table with rows anchored differently.
- **(ii) A NEW purpose-built audit table** (working name `provenance_corrections`) **whose schema
  IS the evidence rule:** `cited_candidate_id NOT NULL REFERENCES candidates`,
  `cited_daily_recommendation_id NOT NULL REFERENCES daily_recommendations`, pre/applied value
  JSON per corrected field, applied_at/applied_by, reason. **The citation becomes structural
  because the schema refuses its absence** — the constraint enforced by construction rather than
  by review. **CHARC leans (ii)**; the §3 architecture pass rides the plan either way (new table
  = schema tripwire; migration is ADDITIVE, no rebuild of anything).

Contemporaneity cannot be a SQLite CHECK (cross-table); it is enforced in the service layer AND
mirrored in `__post_init__` per gotcha #11 — schema + constant + validator in ONE commit.

## 4. GUARDS CARRIED FROM THE SIBLING DEMANDS (each invisible from inside this arc)

- **The Demand-B guard (RD's):** annotation rows — and ANY record written after entry whose
  purpose is post-hoc description, including the Phase-22 abandonment intent — are **PERMANENTLY
  INADMISSIBLE as citations here.** The citation FKs in (ii) make this structural for V1 by
  admitting only the two pre-entry artifact tables; keep it that way deliberately.
- **D36:** if the plan needs an immutability claim about any cited or corrected field, it is
  **verified against the audit trail** (no correction row touching that field), never inferred
  from writer-absence — a column-name grep cannot see the dynamic-SQL corrector.
- **The generic-corrector interaction:** the cohort keys remain reachable through
  `reconciliation_auto_correct.py`'s PRAGMA allowlist when a REAL discrepancy exists. The plan
  must decide and DOCUMENT whether they join `_RESERVED_JOURNAL_FIELDS` (routing them here
  exclusively) — CHARC leans YES for `hypothesis_label`/`candidate_id`/`trade_origin`, the same
  coupled-surface reasoning as `entry_date`.

## 5. THE LIVE CASE — trade 23 (CADL), the acceptance instance

`entry_intent='standard'` already set (backfill-intent, RD-verified). Remaining, all derivable:
`hypothesis_label` NULL → `'A+ baseline (aplus)'` · `candidate_id` NULL → **12341** ·
`trade_origin` `'manual_off_pipeline'` → `'pipeline_aplus'`. Citations: candidate **12341**
(`bucket='aplus'`) and `daily_recommendations` id **172**, both written on the **08-11** action
session; fill **08-12**. Contemporaneity holds with a day to spare. The operator's own
characterization is on record: he read a `today_decision` as a hyp-rec — the record was right,
the read was not. **Application to the live row is an operator-witnessed gate, step by step.**

## 6. DISCRIMINATING TESTS (the brief names them; the plan owns their arithmetic)

1. **The later-record refusal** — a citation whose session anchor POST-dates the fill is refused.
   **Cannot be built from CADL data alone**; the fixture must construct a post-fill citation.
2. **The wrong-anchor discriminator** — a fixture where `evaluation_runs.data_asof_date` differs
   from the cited row's own `action_session_date` such that the WRONG anchor would ACCEPT and the
   right one REFUSES. This is the test that fails an implementation which greps green on CADL.
3. **Free-typing refusal** — no path accepts an operator-supplied label string; the label written
   equals the cohort-derived value even when the operator supplies a conflicting one (or the
   surface takes no label parameter at all — preferred).
4. **Audit round-trip** — correction applied → audit row carries both citation FKs, pre/applied
   values; applied twice → second is a no-op or a clean refusal, never a duplicate write.
5. **Cohort read flips** — before: trade 23 absent from every cohort read; after: present in H1's
   membership *with the monthly-read denominator moving 2/20 → 2/21* (compute the expected values
   under BOTH pre- and post-fix paths per the regression-arithmetic rule).

## 7. PROCESS

Envelope: `swing/trades/` (new service module), `swing/data/` (migration + repo per the §3 pass
riding the plan), `swing/cli.py`. **Declared accepted limitations ride every review prompt, each
WITH its reason, challenge invited.** A-loop per the recipe (stop at first clean verdict;
minors-only self-check; round-5 ledger check-in). **B review = the orchestrator's, at its gate**,
judged under the introduced-vs-banked rule. Dispatch recommendation: **writing-plans at
opus-xhigh** (the audit-shape fork and the evidence semantics are design-dense); **executing at
implementer-opus-high**. Plan routes to CHARC (§3: new table/module) and RD (evidence-rule
fidelity — the encoding of HIS rule is HIS gate) before executing.
