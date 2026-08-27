# PHASE 22 — Scope Proposal (CHARC, 2026-08-23; **operator-RATIFIED AS PROPOSED 2026-08-24**)

**PHASE 22 ACTIVE as of 2026-08-24.** Theme: **THE ORDER-LIFECYCLE GAP + TRUTHFUL-RECORD COMPLETION.** Phase 21 built the latch
execution surface; the boundary wave built the provenance-correction machinery. What three weeks
of live trading has exposed is the seam BETWEEN them: **the framework models the mandate and the
journal models the fill, and nothing models the ORDER in the days it rests at the broker while
the mandate underneath it changes.** Three live instances in three weeks, each a different exit
from the same unmodeled state:

| trade | placed off | mandate then | fill | outcome |
|---|---|---|---|---|
| 20 AMN | 07-27 aplus latch | → `skip` on entry session | 08-07 spike fill | −0.996R; `entry_intent` NULL pending Demand A |
| — VSTS | 07-27 aplus latch | regime undeterminable | operator cancelled 08-03 | 9 days shown ARMED; permanently undeclinable (the §5.1 deadlock); expires 09-08 |
| 25 OII | 08-10 aplus latch (validated, order 1007523377009) | → `watch` 08-12 onward | 08-17 fill | cohort keys EMPTY; the `aplus` citation would REFUSE under the last-word guard (`watch` 12642 is the framework's last pre-fill word) |

Three exits, three different record failures, one root: **`derive_trade_origin` reads "the latest
complete run," and no intent kind can say "this order no longer has a mandate."** Phase 22 closes
the class, not the instances.

## TIER 1 — the class root + the vocabulary it needs

**22-A: entry-path order↔mandate binding (`derive_trade_origin` root fix + latch-on-acceptance).**
Entry recording binds the fill to the RUN THE OPERATOR ACTED ON — the latch/citation graph
(`latch_order_intents` rows exist for OII and were simply never consulted at entry) — instead of
re-deriving from "latest complete run." Folds RD's latch-on-acceptance demand: a broker-accepted
order gets a durable link at ACCEPTANCE time, so the fill inherits provenance instead of guessing.
§3: `swing/trades/` entry-path carve-out + possible schema (an order↔intent link column or table).
**This is the stop-the-bleeding arc: without it, every future resting order that outlives its
screen appearance mints another empty-keys row** (2 in 9 days since Demand C shipped).

**Sharpened by RD's trade-25 ruling (2026-08-24), which is 22-A's governing input:**
- **The citation-graph EXTENSION is in scope:** a fill matched to a broker-validated latch order
  may cite the FIRE candidate + the LATCH VALIDITY row (both contemporaneous, both
  audit-trail-verifiable — the two-tier admission shape already ruled). The last-word guard's
  bucket-series path stays UNTOUCHED for unlatched trades — its refusal of OII's `aplus` citation
  is CORRECT for what the guard is; the latch ladder is a different authority the guard
  structurally cannot see. Scope boundary, not defect.
- **The doctrine bound's second clause governs the semantics:** *a latch dies at its own
  INVALIDATION (rung 4) or above — never of bucket drift* (rung 5 is `criteria_lapsed`,
  report-only by RD's arming ruling). The discriminator is the latch's own FROZEN invalidation —
  a semantic line the fire itself declared — never the bucket.
- **THE ACCEPTANCE TEST IS FULLY SPECIFIED BY THE THREE LIVE CASES and RD will hold the plan to
  it:** from the record alone, 22-A must reproduce AMN (invalidation breached → does NOT label
  from the fire), OII (drift, invalidation untouched, frozen-pivot fill → DOES label from the
  fire), and VSTS (never filled → no label at all). Three exits, three different answers, one
  mechanism.

**22-B: Demand A — `unintended_execution`** (name operator-concurred; §3 pass committed; RD's
two-tier admission endorsed with immutability-verified-against-the-audit-trail). The migration is
a **57-column/13-CHECK `trades` REBUILD** (D30 class; the 0031 pattern, NOT the 0027 shape).
**§VII.F ratification of SPECIFIC AMENDED TEXT (0034 shape: hash-pinned, independently derived)
is a distinct gate inside the arc — the name concurrence was not it.** Applies to trade 20 at a
witnessed gate.

**22-C: abandonment intent** (operator-ratified (d)): records abandonment WITHOUT requiring the
order the framework never offered; `recorded_at` vs `happened_at` honest; **PERMANENTLY
INADMISSIBLE as cohort/intent evidence** (the guard all demands carry). Closes the VSTS deadlock
class — the §5.1 absorbing state gets its exit. Should land before the next stale mandate needs
it, not before 09-08 (VSTS itself expires per ratification).

**Trade 25 OII: RULED (RD, 2026-08-24) — it labels FROM THE FIRE (H1, faithful derivation from
candidate 12284, `standard` intent already set); the 08-17 `watch`-row labeling is REFUSED
outright (it would misfile a mandate fill exactly as `standard` would have misfiled AMN, and H1
— starved at 2/20 — would silently lose a genuine sample to H5). INTERIM: cohort keys stay
EMPTY pending 22-A** — honest NULL over silent wrong, the trade-20 standard; no raw write, no
watch citation. **Calendar consequence, RD-stated:** trade 25 is OPEN and H1 counts CLOSED
trades, so the September read is unaffected unless it closes before 22-A lands — in which case
the read carries it as a NAMED pending-label row, never silently uncounted.

**22-A SPLIT (operator-directed option C, 2026-08-25; RD + CHARC ratified).** 22-A ships the
link + entry-path consultation + the `candidates` barrier + a SINGLE-STATE epoch (armed at the
migration; **the admission reader verifies the barrier triggers EXIST at read time and refuses
structural admission if absent** — the drop's consequence made mechanical) + the six-case gate +
**pre-barrier admission REFUSING outright, no tier-2 escape**. A continuity gap REFUSES (amended
from demotes — nothing to demote to). **22-A2 (PROOF MACHINERY, the follow-on)** owns: the
`[fire_session, read]` continuity interval · the tier-2 conjunction WITH RD's single-rounding-
authority amendment · attestation/replay semantics · retirement/gap/re-arm eras + the third and
fourth epoch triggers + `gap_era_reconstructed` · **trade 25's correction**. The deferred
rulings travel AS RULED, never re-opened; inherited findings (R6-02/03/04, R7-01/02/03/06,
R8-01/02/03) transfer with their evidence as the brief's opening premise-set. **Horizon marker
(RD): if trade 25 has closed, 22-A2 lands before the OCTOBER read.** Split evidence: 10 of 13
recent CRITICALs in the proof machinery; round 8 the clean experiment (no rulings absorbed, all
three criticals in the interval authored one round earlier); 97 findings with ZERO
oscillation — scope, not instability.

## TIER 2 — surfaces that lie

**22-D: trail-surface one-voice** (operator-ratified). The advisory gates on the SAME eligibility
flag the tile renders; which-MA becomes ONE derivation (`advisory.py:483-485` currently fires both
MAs, neither consulting eligibility). **Not gated on RD's §VII.F doctrine read** — his interim
ruling (eligibility governs) fixes the SHAPE now; the doctrine read later moves the threshold, not
the shape.

**22-E: Demand B — the annotation surface** (RD's). Rows inadmissible as evidence by
construction; pairs naturally with 22-C's schema work (possibly one migration family — plan
decides, §3 pass rides it).

## TIER 3 — the sweeps (each a CLASS with ≥3 instances, never per-site patches)

**22-F: handler-escape sweep** — which handler tuples exist, which exception types escape each
(D34 + BANK-1 + BANK-3). **22-G: unactionable-surface sweep** — surfaces presenting what the
operator cannot act on (fixed advisory + BANK-2/D35 + BANK-4); RD's framing rides: an unactionable
surface produces no record of the fill it failed to offer, so it is a measurement gap too.
**22-I: THE REPLACE-EXPOSURE SWEEP (added 2026-08-26, four confirmed instances + one directed
probe).** Every append-only/immutability guard in the schema verified against conflict-resolution
bypass (`INSERT OR REPLACE` / bare `REPLACE` / `INSERT OR IGNORE`), with the measured-probe
standard (control + test, live-DB copy, default `recursive_triggers`). Confirmed exposed:
`candidates` (fixed, 0037) · the epoch (fixed, 0037) · `latch_order_mandate_links` (fixed, leg 4) ·
`provenance_corrections` (fix ruled into 0037). Directed probe: `latch_order_intents` (joins 0037
if exposed — the arc's own evidence source). Banked to this sweep: `latch_view_events` + any
guard the sweep enumerates. **The CONVENTION is the part that ends the class:** an append-only
guard ships as a TRIPLE (`no_update` + `no_delete` + conflict-scoped `no_replace`), plus the
NULL-`WHEN` coverage check on any `WHEN`-clause trigger. **THE PRICED COST, up front (leg 5,
measured): a `BEFORE INSERT` trigger CANNOT distinguish benign conflict resolution from
destructive — `ON CONFLICT ... DO NOTHING` and `OR REPLACE` are indistinguishable to it. So any
table whose production writer uses `ON CONFLICT` needs the WRITER adjusted (a `WHERE NOT EXISTS`
pre-filter so the lost-race path presents no conflict, `ON CONFLICT` retained as the belt) —
NEVER the barrier narrowed**, because narrowing leaves a live conflict target and the measured
consequence of a live `UNIQUE` target is a MOVED id (the id-reuse class). A sweep that meets its
first `ON CONFLICT` writer unpriced will be tempted into exactly the narrowing that silently
reopens the hole. Both directors concur; the writer's observable contract must be pinned by
tests that do not move with the repair. **SECOND PRICED COST (2026-08-26, measured): an OMITTED
`INTEGER PRIMARY KEY` presents as `-1` inside a `BEFORE INSERT` trigger, NOT NULL** — so a PK
conflict clause testing `NEW.<pk>` sees `-1` on every ordinary append, and a stored row with id
`-1` would abort the append path. **The ruled idiom:** the PK clause reads
`(NEW.<pk> != -1 AND <pk> = NEW.<pk>)`; NEW tables additionally carry `CHECK (<pk> > 0)` so a
negative-id row can never exist and the sentinel is unambiguous; EXISTING tables verify
no-negative-ids at sweep time and DECLARE the residual (an explicit `-1` insert is
indistinguishable from omitted; no production writer passes explicit ids). Every site ships the
three-direction discriminating set: ordinary append SUCCEEDS · conflicting REPLACE ABORTS ·
explicit conflicting id ABORTS. RD's framing binds: a REPLACE-mutable
audit table makes the audit-trail check a writer-absence claim one level up.

**22-H: D37+D38 timestamp sweep** — clock-domain normalization at COMPARISONS (never stored data)
off the new `PIPELINE_LOCAL_TIMEZONE` constant + the lexical-TEXT-predicate rule (§3.0 of the
Demand-C plan) applied repo-wide. Scoping input: the orchestrator's READ manifest — 10 live-code
spellings + 7 prose occurrences incl. `web/routes/patterns.py:82` (the prose is #31-class and must
move with the code).

## TIER 4 — riders + leftovers

Wave items 6 (D32 backups retention; composition gate named against item 5's backup default) and
7 (D9 ambient-state sweep) · the **#11-SQL-twin gotcha amendment** (docs-only; **refined by 22-A R5-02: a twin that EXISTS but encodes a WEAKER predicate — trusting a stored grade where the model re-derives — is the same defect; the twin must mirror the AUTHORITY, not the column — **and ACROSS AN ENGINE BOUNDARY, mirroring the authority means CONSUMING ITS OUTPUT, never reimplementing its reasoning** (2026-08-26 ruling: three engine-semantic divergences in three rounds — NaN-JSON, whitespace-strip, type affinity — each a different mechanism; the service computes and PERSISTS the canonical form, SQL compares STORED EQUALITY — a FACT, never a re-derived JUDGMENT)**; 4 instances in one
loop of a model-side rule added without its schema twin) · D33 stays banked (trigger: equity ≥
$7,500).

## SEQUENCING CONSTRAINTS (calendar, not preference)

- **RD's monthly read #3 runs the first trading week of September.** No measurement-path merge
  and no `trades` rebuild lands DURING the read week — 22-B lands before it or after it, never
  across it. RD's clock-domain caution binds the read itself (no cross-domain window comparison
  without normalizing).
- **VSTS expires 09-08** (ratified; nobody touches it).
- 22-A before 22-B if both can't precede the read: the bleeding (new empty-key rows) compounds;
  the vocabulary gap is stable at one row.
- Every arc: A-loop per the delivered recipe; B at the ORCHESTRATOR's gate under
  introduced-vs-banked; declared envelope + accepted limitations WITH reasons in every review
  prompt; plans on `main` before their branch is deletable.

## WHAT PHASE 22 IS NOT

No new detector/pattern work, no research-harness work, no dashboard features. The phase ships
when the record can say what actually happened to every order the framework caused to exist —
including the ones nobody decided to fill and the ones the broker no longer backs.
