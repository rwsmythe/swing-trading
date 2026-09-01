# 22-A -- Entry-path order<->mandate binding (implementation plan)

**Commissioning brief:** [`docs/phase22-arc-a-commissioning-brief.md`](../../phase22-arc-a-commissioning-brief.md)
**as corrected by replacement at `83f15dcf` (2026-08-24)** -- six acceptance cases, the
strict-below boundary ruling, and RD's frozen-value proof requirement. **Phase scope:**
[`docs/phase22-scope-charc.md`](../../phase22-scope-charc.md) Tier 1.
**Plan base:** `938ffca2`. **Live DB at authoring:** `schema_version = 36`, 25 trades, 146
evaluation runs, 4 `latch_order_intents` rows, 1 `provenance_corrections` row.
**RE-MEASURED 2026-08-24 at the round-9 pass: 27 trades, 147 evaluation runs, 5
`latch_order_intents` rows, 1 `provenance_corrections` row** -- the nightly has run since authoring
and added a fifth intent (a DFTX `place`, candidate 12997, no validity row: the RHI shape).
**Every load-bearing premise re-verified against the moved DB and HELD** -- trade 25 is still
`(candidate_id=None, trade_origin='manual_off_pipeline', hypothesis_label=None)`, and intents 1 and
2 are byte-unchanged. **Stated because "the whole table (4 rows)" at S1.2 is an AS-OF claim, and an
as-of claim read as a present-tense one is how a fixture silently stops matching the world.**

This is the WRITING-PLANS deliverable. It carries every premise re-derived against the live DB
and the live code with the command that produced it (S1), the design decisions OWNED with their
reasons and their rejected alternatives (S2), the six binding acceptance cases plus the coverage
this plan adds beyond them (S3), the schema (S4), the module design (S5), the test design (S6),
the TDD task ladder (S7), the accepted limitations WITH their reasons (S8), the operator gate
(S9), and what is flagged rather than fixed (S10).

> ## SCOPE: **RE-SCOPED TO OPTION C, RATIFIED BY BOTH DIRECTORS 2026-08-24.** The proof machinery
> is CARVED OUT to a named arc, **22-A2 (PROOF MACHINERY)** -- carved, not deleted, with its
> doctrine preserved verbatim-liftable at **S12** and its inherited findings listed there.
>
> **22-A KEEPS:** the durable order->mandate link at broker acceptance * the entry-path
> consultation * the `candidates` UPDATE+DELETE barrier * a **SINGLE-STATE epoch** * the six-case
> acceptance gate (5a REFUSE / 5b synthetic ADMIT on the survivorship ground / 6 equality ADMIT) *
> and **pre-barrier admission REFUSING OUTRIGHT, with no tier-2 escape.** Fires from the epoch
> forward admit STRUCTURALLY -- **the bleeding stops going forward, which was the commission.**
>
> **22-A2 TAKES:** the `[fire_session, read]` continuity interval * the tier-2 four-part conjunction
> with RD's single-rounding-authority amendment * attestation and replay semantics * retirement /
> gap / re-arm eras with the third and fourth triggers * `gap_era_reconstructed` * **and trade 25's
> correction.**
>
> **CHARC'S NEW REQUIREMENT, and it is what makes single-state coherent (S2.4d).** He asked whether
> single-state survives his own CONDITION 3 (reversibility, any-drop-recorded) and answered yes --
> *provided the drop's consequence is MECHANICAL rather than procedural*:
>
> > **THE ADMISSION READER VERIFIES THE BARRIER TRIGGERS EXIST AT READ TIME -- a `sqlite_master`
> > check -- AND REFUSES STRUCTURAL ADMISSION IF THEY ARE ABSENT.**
>
> Single-state means armed-and-verifiably-armed-**NOW**, else refuse everything. **That converts
> "any drop is recorded" from something a person must remember into a consequence nobody can
> avoid**: dropping the barrier mechanically halts structural admission. The emergency DROP
> escape-hatch survives; what it can no longer do is leave admission running on a claim the barrier
> no longer backs.
>
> **TWO MORE FINDINGS RESOLVE BY DISSOLUTION -- the FOURTH and FIFTH on this arc.** With the
> existence check in place, **R5-01's third trigger and the CRITICAL routed to CHARC (R7-02's
> fourth) BOTH DISSOLVE for 22-A**: they protect era sequences this arc no longer models. **Both
> holes are REAL and their rulings travel to 22-A2 intact** (S12). *(The earlier two: EXT-4 /
> R6-06, moot when the carve-out was withdrawn; and R8-04, which existed only because read-time
> authority contradicted the stored tier -- see the triage at S12.2.)*
>
> **PLANNING IS COMPLETE. THE OPERATOR RULED IT CLOSED 2026-08-24; CHARC ENDORSED "WITHOUT
> RESERVATION." NO FURTHER REVIEW ROUND WILL BE RUN, AND THAT INSTRUCTION IS DELIBERATE.**
>
> **The argument for stopping is the loop's own evidence.** Round 9 returned 3 CRITICAL + 9 MAJOR +
> 1 MINOR, and the leg that preceded it produced the 10,000-value rounding scan, the 24-row live
> incidence, the `recursive_triggers` grep and `22.13 = 22.13`. **Those are findings a TEST catches
> in seconds and a review round catches one at a time.** *The review never failed -- 110 findings
> across nine counted rounds, ZERO oscillation, not once. It is simply the wrong instrument for
> what remains.*
>
> **THREE CRITICALS AND ONE DIRECTOR-ADDED ITEM ARE FIXED HERE; THE REMAINING TEN ARE RECORDED AT
> S13 AS THE EXECUTING ARC'S OPENING PREMISE-SET**, with their evidence, in the same
> verbatim-liftable form S12 uses for 22-A2. **Every one of the thirteen is dispositioned; none
> falls through.** Fixed: **R9-01** (the barrier check compared NAMES, not bodies -- CHARC ruled the
> repair onto the T1b pinned-DDL precedent and owned the hole as his requirement rather than its
> encoding), **R9-03** (the route deferral had DELETED a live production rejection instead of
> relocating it), **R9-11** (migration `0037` was staged across three commit-tasks, which the
> version gate makes silently unrunnable), and **CHARC's generalisation of this arc's `REPLACE`
> finding -- the `candidates` barrier itself proved fail-open to `REPLACE`, on the arc's
> load-bearing table** (S4.5-replace).
>
> **Two of the inherited findings falsify cases this plan specifies (R9-04, R9-05). They are
> recorded exactly as found rather than quietly corrected** -- an executor inheriting a known-wrong
> case is far better off than one inheriting a silent one.
>
> **What this leg DID land** (all before the round): the five round-8 survivors closed -- **RD's
> SINGLE ROUNDING AUTHORITY** (S4.3a, measured: the Python/SQLite divergence is exactly the
> `.125`/`.625` eighths, **24 live `candidates` rows**), `actual_limit_price` on
> `AcceptedLatchOrder`, the ladder re-derived, `5b-pre` written with the twin roster replaced by a
> closure check, and `$.authorization` input fidelity -- plus **the residual carve sweep** and a
> CRITICAL-grade defect found by executing SQLite rather than reading the plan: **the two-trigger
> epoch was fail-open to `INSERT OR REPLACE`** at the default `recursive_triggers=OFF` (S4.5-epoch).
>
> **NINE counted rounds: 39 CRITICAL + 67 MAJOR + 4 MINOR = 110 findings, zero reopened, zero
> reverted, zero dismissed.** Of the 97 raised before round 9: **92 fixed, 4 travelled to 22-A2, 1
> dissolved.** Full ledger: `.copowers-findings.md`.
>
> *(A sentence fragment stood here -- "2026-08-24 and are encoded here. The next round is the LAST
> before the plan routes to CHARC's section-3 gate and RD's six-case gate." -- an orphaned clause
> whose subject had been edited away, carrying a claim about round counts that four rounds then
> falsified. Struck at the round-9 sweep.)*
>
> **RD WITHDREW THE INVALIDATION CARVE-OUT, AND HIS OWN SESSION-GRAIN RESTATEMENT WITH IT.**
> Fill-wins is UNIFORM, invalidation included; his ORIGINAL bound was right all along and the
> "correction" of it had introduced the error. He re-opened the doctrine **on semantics rather than
> on the corrected dates, so it cannot flip on a third arithmetic.** The ground is a measurement
> argument, not a courtesy: **refusing same-session collapses is SURVIVORSHIP BIAS -- the fastest
> loser is the fill that collapses the day it triggers, and ejecting exactly those trades censors
> H1's left tail and biases its mean UP.** The bound's final form pins the anchor that caused this
> arc's premise error: the breaching close belongs to its **`data_asof`** session, **never
> `action_session_date`** (S2.3.1a). **Case 5b FLIPS to ADMIT; 5a (real AMN) REFUSES as before;
> case 6 unchanged.**
>
> **THE UNWIND WAS THE LARGER HALF OF THE WORK, and it was swept deliberately rather than left to
> inertia.** A cluster of fixes had been built ON the carve-out and became load-bearing for nothing
> the moment it was withdrawn: **R6-01's persisted fill-session-close evidence** (four bound fields
> + cases 45a-45d), **R6-05's rebuilt case 8** and its 8b/8c companions, the **coverage window split
> into "two windows, two owners"**, the withdrawal of **"alive by construction"**, **S0(1)'s
> amendment**, and **EXT-4** -- all struck, each recorded at its site rather than silently reverted.
> **What SURVIVED on its own merits is R6-01's standing rule:** *if a clause can refuse an
> admission, the blob records the input it judged and the verdict it reached, or "passed" and
> "never ran" are indistinguishable at audit.* **The sweep then found FOUR survivors-by-inertia
> after the main pass** -- a stale "nine checks" in case 53b, another in L15, `45a-45d` still sitting
> in Task 11's acceptance, and S2.3.1b still narrowing the rule to three reasons -- **the
> thirteenth instance in this loop of a stale claim and its dependents being two artifacts.**
>
> **AND ONE INVERSION WORTH READING TWICE:** SS-01's "unreachable invalidation branch" was a DEFECT
> under the carve-out and is **the MECHANISM** under fill-wins-uniform. The probe's `bar_bound` ends
> the session BEFORE the fill, so a same-session breach is invisible to it and the mandate admits --
> **which is RD's rule exactly, delivered structurally, with NO comparison authored by this arc**
> (S2.3.1c). Case 28d' pins it, and pins it loudly: if `bar_bound` ever widens, 28d' fails on the
> case that would otherwise silently start refusing 5b and restoring the bias.
>
> **THE OTHER THREE -- AND ALL THREE NOW TRAVEL TO 22-A2 RATHER THAN BEING ENCODED HERE (S11).**
> CHARC APPROVED R6-02 **and widened it** -- continuity required from the **FIRE SESSION to the
> READ**, not from mint (a gap BEFORE the mint is as fatal as one after; RHI is the live proof),
> any gap **DEMOTING to tier-2**, plus the retirement-window byte-identical-restore twin (case 35h).
> RD ruled the tier-2 threshold is **not a number but a BINARY CONJUNCTION OF FOUR**, with depth and
> anchor-strength **ATTESTED, never verdict-bearing**; replay re-evaluates those four, and **context
> drift is never divergence.** **Every one of those governs the continuity interval or the tier-2
> class, both CARVED -- so they are preserved AS RULED at S12 and bind nothing in 22-A.** What
> survives here is R6-02's one-reader half (S4.5C). **EXT-4 / R6-06 is MOOT BY DISSOLUTION.**
>
> > **THE LINE CHARC AND RD REACHED INDEPENDENTLY, now the plan's governing sentence for every
> > stored verdict-shaped value: A STORED GRADE IS AN ATTESTATION OF WHAT WAS VERIFIED AT WRITE
> > TIME; A VERDICT IS COMPUTED AT READ TIME AGAINST THE AUTHORITY.**
>
> > **PREMISE CORRECTION CARRIED UP, MEASURED (S3.5).** The invalidation carve-out reached this
> > plan justified by *"AMN's only breach close is 30.80 on 2026-08-07 ... breach session == fill
> > session."* **Re-derived from the archive: the breach close is 2026-08-06; the fill is
> > 2026-08-07; the fill session's own close is 36.00 and does not breach.** AMN is the
> > PRIOR-SESSION case -- it is case **5a**, not 5b. **The ruling is DOCTRINE and stands on its own
> > terms; what changes is case 5b**, which was specified as "the full AMN geometry" and is now
> > built as an explicitly synthetic variant with the breach session MOVED onto the fill session.
> > Second premise correction of this dispatch, and it landed on the one dimension nobody stated --
> > which is the scrutiny the same ruling asked me to apply to my own synthetics (S3.8).
>
> deliberately NOT a counted round). **The orchestrator ruled at the round-5 gate: NO round 6 --
> a dedicated self-sweep instead, on the ground that eleven of the last nineteen findings were
> residuals of this loop's OWN fixes (the Expansion-#13 cumulative-cascade signature), so a sixth
> review round would mostly rediscover its own wake.** The sweep returned **14 findings, 2 of them
> CRITICAL**, all fixed; the full list is in `.copowers-findings.md` under SELF-SWEEP.
> **The single most important:** the H1 tie rule had thrown a THIRD residual, exactly as the gate
> ruling predicted -- **its `invalidation` branch is UNREACHABLE through the production probe**
> (`bar_bound` is the session BEFORE the fill), so the rule names three reasons, not four, and
> case 28d could never have been built.
> **Every finding from
> every counted round is adjudicated** -- including round 5's ten, which were fixed
> before the gate rather than carried, because round 3 already showed what carrying them costs.
> **The loop is PAUSED for the orchestrator's continuation ruling, per recipe S3.** By the ledger's
> own criterion the composition says CONTINUE: round 5 returned 6 CRITICAL + 4 MAJOR, **all NEW,
> zero reopened, zero oscillation, zero dismissed across the whole loop** -- but the gate-holder
> decides, not the author.
>
> **NOTHING BLOCKS EXECUTION. BOTH CONDITION-4 EXCEPTIONS WERE RULED AND APPROVED 2026-08-24
> (S4.5B), AND TASKS 2 AND 11 ARE UNBLOCKED.** *(This block previously read "TWO ITEMS NOW BLOCK
> EXECUTION ... Task 2 and Task 11 do not execute until CHARC rules on these." **Stale blocking text
> is a distinct and worse failure than stale description: it stops an executor on a decision that
> has already been made** -- review 22A-R6-13 caught the same shape in S7 and this instance survived
> it in the header, which is the survivors-by-inertia class exactly.)* **The epoch ask is still
> THREE `CREATE TRIGGER`s and the third one's PURPOSE changed at the Option-C carve** -- from
> guarding an ERA SEQUENCE to closing a measured `INSERT OR REPLACE` hole -- **surfaced for CHARC's
> gate at S11 rather than absorbed.**
>
> **The two rulings this plan was waiting on arrived 2026-08-24 and are encoded as POLICY INPUTS,
> not as the plan's own judgment** -- each recorded at its site with the authority that made it:
>
> * **RD, DECISION 2 -- pre-barrier admission REFUSES BY DEFAULT** (S1.5.3), conditioned exactly as
>   this plan proposed. **THIS HALF IS WHAT 22-A ENCODES, AND IT IS THE WHOLE OF RUNG 9 HERE.**
>   *(His ruling also created a TIER-2 pre-barrier admission class -- an IMMUTABLE EXTERNAL
>   contemporaneous record of the frozen values, recorded before the outcome was known and
>   tamper-evident since, matching the current candidate row at the mandate grain, which trade 25
>   qualifies for on evidence re-derived at S1.5.4. **That half is CARVED to 22-A2 (S12), AS RULED,
>   and with it goes trade 25's correction** -- S8-L2c states the cost.)*
> * **CHARC, DECISION 1 -- all three envelope extensions APPROVED; the `candidates` barrier
>   APPROVED with FOUR BINDING CONDITIONS** (S4.5A), one of which -- CONDITION 4, the migration is
>   ADDITIVE -- **this plan reports it must exceed by TWO CREATE TRIGGERs, and routes rather than
>   takes** (S4.5B).
>
> **Ledger:** round 0 VOIDED (pre-ruling artifact) * round 1 = 3C + 11M, all fixed * round 2a
> DISQUALIFIED (no footer; **its content was later HARVESTED -- see below**) * round 2b = 6C + 8M +
> 1m, all fixed * round 3 = 5C + 7M, **all ten remaining now fixed** * round 4 = see
> `.copowers-findings.md`. Verbatim transcripts + per-finding dispositions live there.
>
> **THE HARVEST OF ROUND 2a.** That round was disqualified mid-write on an absent `tokens used`
> footer. The disqualification was correct about what its author saw and stays a disqualification
> -- it counts toward nothing -- but at the orchestrator's QA the file was COMPLETE (12,323 lines,
> real summary, footer, verdict on the last line): the codex process had kept running and finished
> after he read it. **Its thirteen findings were therefore a full `strong` round's content that had
> never been adjudicated**, and they are adjudicated now. Nine deduped against findings rounds 2b
> and 3 had independently produced. **FOUR did not**, and three of those were LIVE defects in the
> committed plan:
>
> * **H1 (from 22A-REV-04) -- the largest single finding of the whole loop.** Excluding the subject
>   trade from the probe DELETES the shipped ladder's rank-0 same-session fill precedence, so a
>   valid latched fill dated exactly ON its mandate's horizon / decline / supersession session is
>   FALSELY REFUSED -- the arc minting the very empty-cohort-key row it exists to stop. Fixed in
>   S2.3.1a with the tie rule imported from the ladder rather than re-spelled.
> * **H2 (from 22A-REV-12) -- a LIVE contradiction in S2.1**: the link-shape paragraph still
>   instructed the minting trigger to copy `zone_cap` "from `candidates`", a column `candidates`
>   does not have (`0001_phase1_initial.sql:24-41`, read in full), in the same section that removes
>   the stored cap. A residual of round 1's own AR-14 fix that the class-sweep missed.
> * **H3 (from 22A-REV-13) -- a LIVE truncated sentence** at S2.3.1: the `horizon`-as-a-killer
>   argument, which is ROUTED TO RD, broke off mid-clause and ran into the next heading, so the
>   rationale was absent at its own decision site.
> * **H4 (from 22A-REV-10) -- a nondiscriminating fixture**, and the live DB sharpens it beyond
>   what the reviewer could see: trade 25's `hypothesis_label` **is NULL on the real row**
>   (measured), so case 5 inheriting case 1's real shape asserts NULL against a fixture that had
>   nothing else to write. Case 5 now SEEDS a non-NULL submitted label.
>
> Three more (H5-H7) were refinements of already-fixed findings and are folded at their sites.
>
> **Round 3's ten, all now fixed:** R3-01 `BEGIN IMMEDIATE` + the no-link->link race (S2.2) *
> R3-02 consumption survives fill replacement (S2.4a) * R3-03 three-valued competitor liveness
> (S2.4b) * R3-04 governing place cycle + cancellation history (S2.4c) * R3-05 the price guard
> uses `mandate_limit_price`, not a second rounding (S2.4.1) * R3-06 probe selection by
> `candidate_set` membership (S2.3) * R3-07 epoch immutability (S4.5B, ROUTED) * R3-08 the id
> boundary's claim narrowed to what it proves (S4.5B) * R3-09 `candidate_criteria` is not frozen
> (S2.6.5 + L13) * R3-10/R3-12 trigger claim narrowed + RD's ruling encoded (S4.3, S1.5.3a).
>
> **ROUND 4 (3C + 6M) and ROUND 5 (6C + 4M), all fixed.** The pattern worth naming for whoever
> reads this next -- **and the figure is CORRECTED here, because the first one I published was an
> impression rather than a read (SELF-SWEEP SS-13, and it is the same defect shape as the
> "forty-five clause rows" I caught earlier: a number taken from a feeling of how many, not from
> counting them).** I reported SIX of nineteen to the orchestrator. Classified by reading each
> finding and asking whether it exists because an EARLIER FIX IN THIS LOOP was applied
> incompletely, the answer is **ELEVEN** -- R4-03, R4-05, R4-06, R4-07, R4-09, R5-01, R5-02, R5-03,
> R5-06, R5-09, R5-10 -- **and FOURTEEN** if the adjacent class is included (R4-04, R5-05, R5-08:
> incompleteness in design newly authored in this same dispatch). Only R4-01, R4-02, R4-08, R5-04
> and R5-07 were defects that pre-dated this dispatch's edits. **The understatement mattered
> beyond bookkeeping: the gate ruling was argued partly on that ratio, and the true figure
> STRENGTHENS the ruling it was used to support** -- which is the one direction an error like this
> is allowed to run without needing to be re-decided. Examples of the class: a column
> count that moved 6->7 and left three paraphrases behind; a tie rule stated in the design and
> never propagated into the SQL schema that would have rejected its own admissions; a `-pre` twin
> convention stated universally that would have reversed the verdict of the arc's headline case; an
> archive re-read deleted in round 2b and still sitting three sentences below its own deletion; a
> routed trigger count that moved AFTER it was routed; and a "the ONE place we exceed CONDITION 4"
> claim the plan itself contradicted three pages earlier. **Stating a class once is not sweeping
> for it** -- the sweep now greps for the REJECTED MECHANISM and for every PARAPHRASE of a count,
> never for the finding's label.

---

## S0. THE HEADLINE

Two findings shape everything below.

> **(1) The JUDGMENT already exists.** `swing/latches/service.py:derive_latches` implements RD's
> full precedence ladder including the invalidation rung, gated by his own constraint 6. This arc
> authors NO second invalidation comparison. It authors a **link**, a **consultation**, and the
> **guards that make the consultation sound**.
>
> **(2) The NUMBER is not provable today, and RD's gate requires it to be.** The invalidation
> lives on `candidates.initial_stop` of the fire row, which has ONE writer, **no barrier**, and no
> audit trail. So this arc makes `candidates` **structurally immutable from migration 0037
> onward** (a mandatory `BEFORE UPDATE` **and `BEFORE DELETE`** barrier, Task 2 -- not the
> separable nicety my first draft made it), and additionally snapshots pivot/stop at acceptance and
> cross-checks the snapshot at every comparison as drift DETECTION. **For fires created after 0037
> the live read IS the fire's frozen value, structurally. For fires created BEFORE 0037 -- which is
> every fire that exists today, including OII's 12284 -- no structural proof is available and this
> plan does not pretend one is.**
>
> **(3) RD RULED IT, 2026-08-24, and the ruling is a POLICY INPUT this plan encodes rather than a
> judgment it makes.** Pre-barrier admission **REFUSES BY DEFAULT** -- S9's previously
> unconditional verdict is conditioned exactly as review 22A-R3-12 demanded, and this ruling is the
> policy input it conditions on. A **TIER-2** pre-barrier admission class exists (the Demand-A
> two-tier shape reused): an IMMUTABLE EXTERNAL contemporaneous record of the frozen values,
> recorded before the outcome was known and tamper-evident since, matching the current candidate
> row on every compared field at the mandate grain (`PRICE_DP`). **Operator recollection does not
> qualify. Writer-absence does not qualify.** The correction row records the TIER, the evidence
> CITATION, and the UNCOVERED WINDOW explicitly. Trade 25 qualifies (S1.5.4, re-derived here).
>
> **(4) CHARC RULED THE ENVELOPE AND THE BARRIER, 2026-08-24.** All three extensions approved;
> EXT-2 was **never optional** (without it the arc's own fix is unreachable through the production
> route -- the byte-parity-vs-production-path gotcha as an architecture); the barrier approved for
> UPDATE **and DELETE**, with four binding conditions carried verbatim at S4.5A.

Run read-only against the live DB, as-of each fill session, with that fill's own trade excluded
from the input -- the exact world `record_entry` sees before its INSERT -- the shipped derivation
returns:

| case | probe | shipped `derive_latches` answer |
|---|---|---|
| OII trade 25 | as-of `2026-08-17` | fire 12284 `clear_reason=None` (armed), `bars_through=2026-08-14` |
| AMN trade 20 | as-of `2026-08-07` | fire 11926 `clear_reason='invalidation'` @ `2026-08-06` |
| RHI trade 24 | as-of `2026-08-14` | fire 12442 `clear_reason=None` (armed), `bars_through=2026-08-13` |
| VSTS | never filled | fire 11629 `clear_reason='invalidation'` @ `2026-08-14` |

**AMN is the NO-LATCH FALLBACK control, not an invalidation control** (brief case 2, corrected):
it has ZERO latch rows, so it never reaches the comparison through this path at all. That
correction is the reason the acceptance gate went from three cases to six, and this plan treats it
as the governing fact rather than a footnote.

### S0.1 ENVELOPE, AND THE EXTENSIONS THIS PLAN REQUESTS

Brief S7 envelope: `swing/trades/` + `swing/data/` + `swing/cli.py`. Three extensions are
REQUESTED, each with its exact diff shape and its fallback. **None is taken without a ruling.**

* **EXT-1 (`swing/latches/reader.py`, THREE additive keyword-only parameters).**
  `build_latch_derivation(..., criteria_lapse_armed_override: bool | None = None,
  exclude_trade_ids: frozenset[int] | None = None, strict_decisions: bool = False)`. The first forces the `criteria_lapsed` rung
  OFF -- RD's bound says a latch NEVER dies of drift, and `criteria_lapsed` IS the drift rung
  (S2.3.4). The second excludes the SUBJECT trade on the correction path; **without it the probe
  sees trade 25's own fill, returns `clear_reason='fill'`, and the live application in S9 is
  unreachable** (S2.3, verified against the live DB).
  **APPROVED as specified (CHARC, 2026-08-24)** -- the two no-fallback parameters are correct,
  because *a fallback would silently reintroduce the guessing this arc exists to kill.*
  **Fallback for the first, recorded but not taken:** `dataclasses.replace(cfg,
  latches=replace(cfg.latches, criteria_lapse_armed=False))` -- works today but is enforceable by
  nothing (#31).
  The third makes `load_decision_intents` RAISE instead of silently returning `{}` on a read
  failure, without which a lost decline ledger is indistinguishable from no decline at all (S2.3.3b).
  **There is no fallback for the second or the third**; without the second the arc cannot correct
  trade 25, and without the third it can admit a DECLINED mandate. I would rather say that than
  design around it.
* **EXT-2 (`swing/web/routes/trades.py`).** Two changes, both required for soundness rather than
  polish: (a) the tier-(e) guard at `:1263-1268` calls `derive_trade_origin` a SECOND time as a
  rejection gate, so without it a latched fill submitted WITH a `pattern_evaluation_id` anchor is
  REJECTED by the route before `record_entry` runs -- the arc's own fix unreachable through the
  production form (#31, cross-site composition); (b) the hidden-envelope value-shape ladder at
  `:1040-1075` validates `entry_date` / `entry_price` / `shares` but **NOT** `schwab_order_id`,
  which this arc promotes to a provenance-bearing key (S2.4.1).
  **APPROVED (CHARC, 2026-08-24), and the ruling states it was never optional:** without (a) the
  tier-(e) guard refuses latched fills at POST before `record_entry` runs, so the mechanism is
  unreachable through the production route -- *"an arc whose acceptance test passes only through a
  test harness is the byte-parity-vs-production-path gotcha as an architecture."* The former
  fallback for (a) is therefore WITHDRAWN, not merely disfavoured; (b) ships too.
* ~~**EXT-4 (`swing/latches/service.py`, ONE extraction).**~~ **WITHDRAWN 2026-08-24 -- MOOT BY
  DISSOLUTION.** It existed only to single-source a fill-session invalidation comparison, and RD's
  withdrawal of the session-inclusive carve-out means no such comparison exists (S2.3.1c). **The
  entry is struck rather than deleted because CHARC named the class:** *an envelope extension that
  dissolves under a corrected premise was never an extension request -- it was the premise asking
  for scaffolding.* **The envelope is the THREE approved extensions and nothing more.**
* **EXT-3 (`swing/web/view_models/trades.py`, the entry-form label prefill).** **APPROVED as
  OPTIONAL (CHARC, 2026-08-24) -- the implementer's call.** Without it the framework silently
  replaces an operator-visible prefilled label (S2.6.3).
  **Fallback:** S8-L4 declares the residual with a WARNING log and names it as a follow-on.

**No new dependency. No `swing/pipeline/` touch. No measurement-chain change.** One migration
(0037): one new table with its append-only triggers and a general backfill, **SIX** `ADD COLUMN`s
on `provenance_corrections` (**a seventh, RD's tier-2 citation column, is CARVED to 22-A2 -- S4.3,
S12**), two trigger replacements, and -- **mandatorily, as the arc's proof** --
the `candidates` UPDATE + DELETE barrier plus the one-row immutability epoch (S4.5). **No table
rebuild, nothing dropped except the two `provenance_corrections` triggers this migration
immediately re-creates, and no existing row is mutated** -- S4.3 explains why the cross-column
rules live in triggers. **CONDITION 4 is exceeded in TWO places, BOTH APPROVED (S4.5B): THREE `CREATE TRIGGER`s on the
epoch table, and the two `DROP TRIGGER`s that transactionally replace the `provenance_corrections`
triggers.** *(The COUNT of epoch triggers is unchanged by the carve, but the THIRD one's PURPOSE
changed: CHARC approved a trigger guarding an ERA SEQUENCE, which single-state cannot represent,
and its place is taken by a `BEFORE INSERT` barrier that closes an `INSERT OR REPLACE` hole
**measured open at SQLite's default** -- S4.5-epoch. Surfaced at his gate rather than absorbed.)*

### S0.2 WHAT CHANGED FROM THE FIRST DRAFT, AND WHY

The first draft was written against the superseded brief and reviewed in a round that is **VOID**
(it reviewed an artifact the rulings had already replaced; recorded as such in
`.copowers-findings.md`). Its findings were read and acted on anyway -- the gate is on ending the
loop, not on using the content. Seven changes carry from it, each named at its site: the
coverage gate (S2.3.3), the envelope-trust ladder (S2.4.1), the removal of an **unmeasured claim I
had stated as a measurement** (S1.9), the `keys_not_derivable` rule (S2.6.4), the seam reordering
that makes the LOCK provable (S2.2), a narrowed RHI claim (S1.4), and JSON evidence validation in
the audit trigger (S4.3). Two changes carry from the corrected brief: six first-class cases with
the -0.05 breach geometry and the ruled strict-below boundary (S3), and RD's frozen-value proof
requirement, which **changed the link-shape decision** (S2.1).

---

## S1. PREMISES, RE-DERIVED

Every claim carries the command that produced it. DB reads used
`sqlite3.connect('file:<db>?mode=ro', uri=True)`. **Counts state the method that produced them**:
"the whole table" means every row was read and printed; "grep" says what the grep can and cannot
see.

### S1.1 The root

`swing/trades/origin.py:52 derive_trade_origin` resolves the bucket from
`_latest_complete_evaluation_run_id(conn)` (`:27`). Read in full: 20 lines, no other input.
`swing/trades/entry.py:264` is its sole production consumer for the persisted value. **CONFIRMED.**

Neither `trades` nor `fills` carries an order/latch link column. Method:
`SELECT sql FROM sqlite_master WHERE name IN ('trades','fills')`, read in full. **CONFIRMED.**

### S1.2 The whole `latch_order_intents` table (4 rows)

`SELECT * FROM latch_order_intents ORDER BY intent_id`, every row printed with every non-NULL
column.

| intent | kind | cand | ticker | session | key facts |
|---|---|---|---|---|---|
| 1 | `place` | 12284 | OII | 2026-08-10 | fw stop **53.98**, limit **55.59**, qty **2**, `derivation_regime_close=47.97` @ `2026-08-07` |
| 2 | `validity` | 12284 | OII | 2026-08-10 | `validated_place_intent_id=1`, `validity_outcome='accepted_by_broker'`, `actual_broker_order_id='1007523377009'`, `actual_quantity=2`, `actual_stop_price=53.98`, `actual_limit_price=55.59` |
| 3 | `place` | 12341 | CADL | 2026-08-11 | no validity row |
| 4 | `place` | 12442 | RHI | 2026-08-13 | no validity row |

`SELECT COUNT(*) FROM latch_order_intents WHERE ticker='AMN'` -> **0**. The ledger shipped at
`d5d03bb9` on 2026-08-03; AMN's order predates it.

### S1.3 The acceptance gate could not fail an omitting implementation -- CONFIRMED, and this is the arc's governing fact

Re-derived independently of the brief's correction, and it agrees:

* AMN never reaches an invalidation comparison because it has **no acceptance row** (S1.2). Any
  implementation gated on a broker-validated latch order falls through before any judgment.
* OII's fire was never approached: archive closes `2026-08-10..2026-08-14` are
  `51.12, 50.76, 51.02, 51.35, 52.20` against a frozen invalidation of `41.42` -- a 19% margin.
  Method: `swing.latches.reader.load_bars_with_status(cfg, 'OII', start=2026-08-10, end=2026-08-18)`,
  `status='ok'`.
* RHI has no acceptance row; VSTS never filled.

So the brief's six cases, and this plan's additional coverage in S3.7, exist because **a gate
assembled only from states the ledger happens to hold inherits the ledger's coverage**.

### S1.4 RHI -- the live discriminator, claim NARROWED

RHI (trade 24) carries `place` intent 4 on candidate **12442** with **no validity row**; trade 24's
`candidate_id` is **12518** (the 08-14 `watch` row). Both CONFIRMED by direct read. Its latch was
ARMED at its own fill session (S0 table). Its fill price `44.20` and quantity `3` sit inside the
frozen zone `[44.18, 45.5054]` with `framework_quantity=3`.

**Correction to my first draft, which overstated this.** I wrote that RHI would also be matched by
"an implementation keying on the windowed price heuristic". That is FALSE of the shipped heuristic:
`swing/latches/service.py:_match_fill`'s windowed rung requires `entry.candidate_id is None`, and
RHI's is `12518`. RHI therefore discriminates **two** designs -- keying on any latch row, and
keying on an armed latch -- not three. A third fixture (S3.4b: `candidate_id` NULL, in-zone price,
no validity row) is added to discriminate the price-heuristic design, because RHI cannot.

**The divergence the brief asks the plan to speak to** (latch cites 12442, trade carries 12518):
the mechanism keys on the ACCEPTED ORDER, never on `trades.candidate_id`, so a divergence is not
consulted and cannot mislead it. Where the mechanism ADMITS, it OVERWRITES `candidate_id` with the
fire and logs the prior value at WARNING (S2.5). Where it declines -- RHI's case -- it touches
nothing. A standing consequence of the divergence is flagged, not fixed, at S10-F2.

### S1.5 THE FROZEN VALUE -- RD's gate, and the proof this plan offers

The brief's correction is right in every particular: `framework_stop_price = 53.98` is the PIVOT;
the invalidation is `candidates.initial_stop` of the fire (OII `41.41999816894531`, AMN
`30.850000381469727`); the only `invalidation`-named column is `trades.invalidation_condition`
(method: case-insensitive grep for `invalidation` across all 36 migrations -- that column and prose
only); and trade 25's own `initial_stop` is `37.89`, not the fire's `41.42`.

**RD's standard, verbatim: the number compared must be PROVABLY the fire's frozen value at
comparison time**, by audit-trail evidence or by snapshot-at-latch. A bare "candidates is
append-only" sentence does not pass. **This plan chooses the SNAPSHOT, and here is why the other
proof does not carry on its own.**

#### S1.5.1 What is true today, with the search that established it -- and why it is NOT a proof

* ONE writer: `swing/data/repos/candidates.py:41 insert_candidates`, a plain `INSERT`. Method:
  case-insensitive grep for `(insert|update|delete|replace)[^"']{0,40}candidates` across
  `swing/**/*.py` -- 11 hits, one write, the rest imports/SELECTs/prose.
* The D36 un-greppable writer cannot reach it: `swing/trades/reconciliation_auto_correct.py`
  interpolates a `PRAGMA table_info`-validated column name into dynamic SQL (`:298-318`), but its
  `affected_table` is one of FOUR module constants -- `'fills'`, `'trades'`, `'cash_movements'`,
  `'account_equity_snapshots'` (`:511-514`). This is a READ of the constant block, not a grep for
  the table name.
* Migration history: `0001` create, `0012` two `ADD COLUMN`s, and reference-only elsewhere.
  Method: grep all 36 migrations for `alter table candidates|update candidates|drop table
  candidates|insert into candidates` -- two hits, both `0012`.
* **No barrier exists.** No trigger on `candidates`. `swing/latches/identity.py:11` asserts "no
  UPDATE/DELETE path exists for candidates" -- true today, unenforceable, and the #31 shape.

**Every line above is writer-absence.** D36 says exactly that this is not evidence, and RD says a
shelf-lifed claim does not pass his gate. So it is recorded as context, not offered as proof.

#### S1.5.2 The contemporaneous artifact that exists -- and a claim I have to DOWNGRADE

The nightly briefing for the 2026-08-10 session (produced the evening of 2026-08-07) reads:

```
exports/2026-08-10/briefing.md:13
### OII - Buy-stop $53.98 - 2 sh - $28.34 risk = 2 x ($55.59 cap - $41.42 stop)
exports/2026-08-10/briefing.md:94
|  | OII | $47.97 | $53.98 | -11.13% | 4.9% | $37.89 | watch |
```

**My first draft called this an INDEPENDENT contemporaneous writer agreeing with the DB. That is
WRONG and the review caught it.** `swing/rendering/briefing.py:114-118` renders from
`inputs.recommendations` -- the `daily_recommendations` rows -- and those rows are built from the
same candidate pivot/stop, and are **mutable in place**: `upsert_recommendation`'s
`ON CONFLICT ... DO UPDATE SET` rewrites `action_text` and `stop_target`
(`swing/data/repos/recommendations.py:9-27`). So the briefing and the DR row are ONE derivation
rendered twice, not two.

**What the artifact IS, stated at its real strength:** a **contemporaneous DERIVED COPY in a
non-DB file**, one hop from the candidate (candidate(t) -> DR(t) -> briefing file(t)), written at
time t and not rewritten unless the pipeline re-runs that session. It is evidence about what the
candidate said in August; it is not independent of the DB derivation, and it is not immutable.
**It does not clear RD's gate on its own, and S1.5.3 no longer claims it does.**

**Line 94 remains documentary and is worth keeping for a different reason:** the same page shows
OII's WATCH-pool stop as `$37.89` -- exactly what trade 25 carries. Two stops for one ticker on one
page, and the wrong one reached the trade row. That goes into a code comment at the comparison
site.

**Reach:** AMN's 2026-08-03 briefing reads `### AMN - Buy-stop $36.27 - 6 sh - $33 risk` with **no
cap/stop breakdown** -- the older emit format did not carry it. AMN needs none (no acceptance row).

#### S1.5.3 The proof this plan offers -- immutability made STRUCTURAL, forward only

My first draft offered "snapshot at acceptance + cross-check at comparison" as the proof. **The
review showed it is not one, and the argument is decisive:** the fire is created on the evening of
T-1 and the acceptance can be recorded days later (OII: fire 2026-08-07 evening, acceptance
2026-08-10T02:44). **A mutation between fire and acceptance is copied INTO the snapshot and passes
every later cross-check.** The snapshot proves the value did not move AFTER acceptance -- which is
not what RD asked.

**The proof, restructured:**

* **Fires created from migration 0037 onward.** `candidates` gains a mandatory
  `BEFORE UPDATE` **and `BEFORE DELETE`** `RAISE(ABORT)` barrier (S4.5, now **Task 2 and NOT
  separable**). From that point a candidate row cannot change after INSERT, so the value
  `derive_latches` reads live IS the value the fire declared. **That is RD's first proof --
  immutability -- made structural rather than asserted**, which is the only form that survives
  D36's objection that writer-absence is a claim with a shelf life. Recorded as
  `freeze_tier='live_at_acceptance'`; admits structurally.
* **Fires created BEFORE 0037** -- every fire that exists today, including OII's 12284. **No
  structural proof is available**, because the barrier cannot reach backwards and the snapshot
  cannot either. The link row records `freeze_tier='pre_barrier_reconstructed'`, and S1.5.2's
  artifact is contemporaneous-but-derived corroboration, not proof.
* **The acceptance snapshot and its cross-check are retained**, demoted to what they actually are:
  **drift DETECTION** over the pre-barrier window and defence in depth after it. A mismatch
  REFUSES (`frozen_value_drift`); a NULL snapshot refuses (`frozen_value_unavailable`).

#### S1.5.3a RD'S RULING, 2026-08-24 -- the question this section routed is ANSWERED

Review 22A-R3-12 was right that the plan could not carry an unconditional OII verdict beside an
open proof question, and my first two drafts did. **The question went to RD and he ruled. This
subsection encodes his ruling as a POLICY INPUT; it is not the plan's judgment and the plan does
not re-derive it.**

**(1) PRE-BARRIER ADMISSION REFUSES BY DEFAULT.** A `pre_barrier_reconstructed` link is NOT
admitted by the resolver on the strength of its tier. The decline reason is
`pre_barrier_unproven`. This is the exact conditioning 22A-R3-12 demanded, and the ruling is what
it conditions on. **Consequence stated plainly: on the day 0037 lands, the ENTRY path admits
NOTHING, because every fire that exists today is pre-barrier.** The mechanism becomes structurally
live for the first fire created after the migration -- nine mandates have ever existed and seven
are post-epoch (`docs/rd-state.md` line 57 at `9f315cc6`, read directly), so that is weeks away,
not months. The arc still stops the bleeding for every future resting order, which is what it was
commissioned for, and **the plan says this rather than letting the acceptance suite's green imply
a live mechanism.**

**(2) THE TIER-2 CLASS IS CARVED OUT OF THIS ARC (Option C, 2026-08-24) -- pre-barrier admission
REFUSES OUTRIGHT, with no evidence path.** RD's tier-2 class, its four-part binary conjunction, its
attestation and replay semantics and **trade 25's correction** all move to **22-A2**, preserved
verbatim-liftable at **S12**. **They travel AS RULED, not as questions** (RD's binding condition):
22-A2 encodes settled doctrine, it does not re-derive it.

**What that leaves 22-A, stated plainly rather than softened:** on the day 0037 lands the entry path
admits **nothing**, because every fire that exists today is pre-barrier -- and **it stays that way
until the first A+ fire created after the migration**, which at nine mandates ever and seven
post-epoch (`docs/rd-state.md` line 57 at `9f315cc6`) is weeks away. **The arc still stops the
bleeding for every future resting order, which is the commission.** No live row is corrected by
this arc.

**THE NAMED COST, WITH ITS DATE (RD, 2026-08-24).** **Trade 25 keeps a PENDING-LABEL row, and that
row governs every monthly read until 22-A2 lands.** Tolerable for one read; increasingly costly
after. **22-A2 should land before the OCTOBER read if trade 25 has closed by then.** Recorded here
as a cost with a date rather than as a deferral without one.


### S1.6 The `pattern_evaluations` precedent, and three facts about it

`swing/trades/entry.py:352-373`: when `req.pattern_evaluation_id` is non-NULL, `candidate_id`
resolves via `pattern_evaluations.pipeline_run_id -> pipeline_runs.evaluation_run_id`, with
`_latest_complete_evaluation_run_id` as fallback. **CONFIRMED, read in full.**

1. **It resolves `candidate_id` ONLY**; `trade_origin` still comes from the latest-complete read at
   `:264`, computed before the chain runs.
2. **Its anchor is the FORM RENDER, not the mandate** -- its own comment says so. Better than
   "latest", still a proxy.
3. **It is gated on `derived_origin != 'manual_off_pipeline'`** (`:353`), which is why OII has BOTH
   keys NULL rather than one.

**PRECEDENCE (S2.5): the latch link wins**, because it is keyed to a broker-accepted order rather
than to a render, and it is the only one of the two contemporaneous with the MANDATE. Disagreements
are logged at WARNING naming both ids.

**A caller-supplied `req.candidate_id` is unreachable in production.** Method: grep `EntryRequest(`
across `swing/` -> exactly TWO sites (`swing/cli.py:747`, `swing/web/routes/trades.py:1297`), both
read in full, **neither passes `candidate_id`**.

### S1.7 Reading `Latch.state` instead of `Latch.clear_reason` would silently violate RD's bound

`swing/latches/service.py:68-75` maps `declined`, `horizon` AND `criteria_lapsed` all to
`horizon_expired`. The module's own comment (`:66-67`) says so and pins the obligation caller-side
by test, citing #31. A resolver written as `if latch.state == "armed"` would treat a
`criteria_lapsed` latch -- the DRIFT rung RD's bound says must never kill a latch -- as dead, and no
live case would show it because `criteria_lapse_armed` is `False` (verified:
`cfg.latches.criteria_lapse_armed = False`). The resolver reads `clear_reason`; S3.7 case 10 is the
case that fails an implementation reading `state`.

### S1.8 The Demand-C ladder: the last-word guard is the ONLY blocker for trade 25 -- MEASURED

**Probe 1, unmodified service.** `preview_cohort_provenance_correction(conn, trade_id=25,
cited_candidate_id=12284, cited_recommendation_id=169, reason=...)` refuses with exactly one
message: *"candidate 12284 is NOT the framework's last word before the fill: candidate 12642
(evaluation run 141, action session 2026-08-17) is later and also pre-dates the fill."*

**Probe 2, with `_assert_last_word_before_the_fill` monkeypatched to a no-op and nothing else
changed** -- the entire remaining ladder PASSES and derives:

```
post_values = {'trades.hypothesis_label': 'A+ baseline (aplus)',
               'trades.candidate_id': 12284,
               'trades.trade_origin': 'pipeline_aplus'}
cited: DR 169, eval run 136, pipeline run 150, hypothesis 1 'A+ baseline', history row 1
anchors: candidate/recommendation action session 2026-08-10; entry fill 48 session 2026-08-17
window: run_ts 2026-08-07T17:30:02 (raw) / 2026-08-08T03:30:02 (utc);
        pipeline finished 2026-08-07T17:39:07 (raw) / upper 2026-08-08T03:39:07 (utc)
derivation_rule_version = 2026-08-13.3
```

That is the S9 live-application outcome, verified before the plan was written, and it bounds Task
10: replace ONE guard, record the tier.

### S1.9 The fill side already carries the order id -- and a claim I had to withdraw

`fills.schwab_source_value_json` for fill 48 (trade 25's entry fill):

```
{"entry_date": "2026-08-17", "entry_date_source": "execution_leg", "entry_price": 53.98,
 "schwab_instrument_symbol": "OII", "schwab_order_id": "1007523377009", "shares": 2}
```

`latch_order_intents` intent 2 carries `actual_broker_order_id = '1007523377009'`. **The link
already exists in the data; nothing has ever read it.** The envelope is written at exactly ONE site
(`swing/trades/entry_auto_fill.py:463-476`), carried into `record_entry` as
`EntryRequest.schwab_source_value_json` (`swing/trades/entry.py:161`) and persisted verbatim onto
the fill (`:483`).

Trade 20's envelope carries `"schwab_order_id": "1007427919619"`,
`fill_origin='schwab_auto_then_operator_corrected'`, and an `operator_corrected_value_json` moving
the date from `2026-08-01` to `2026-08-07`. The plan uses `req.entry_date` -- the corrected value,
already validated date-only at `entry.py:290-300`.

**WITHDRAWN CLAIM.** My first draft asserted that "probing as-of the Schwab date `2026-08-01` finds
AMN's latch ARMED". **I never measured that; I measured only as-of `2026-08-07`.** It is also
false: `swing/latches/reader.py:895-905` scopes fires to `action_session_date <= horizon_session`,
and AMN's fire is dated `2026-08-03`, so an as-of-`2026-08-01` probe excludes the fire entirely and
returns `fire_not_derivable`. Stating an inference as a measurement is the exact defect this
project keeps paying for, and it is recorded here rather than quietly deleted. The
corrected-date discriminator moves to S3.5c with a date that is actually inside the window
(`2026-08-04`, after the fire and before the breach).

### S1.10 Everything else the plan leans on

* `latch_horizon_sessions(cfg)` = `cfg.pipeline.observe_max_pending_window_sessions` = **30**.
* `PRICE_DP = 2`, single-sourced at `swing/latches/constants.py:91`, with an existing
  anti-re-consolidation test.
* The invalidation comparison is `round(bar.close, PRICE_DP) < round(draft.stop, PRICE_DP)`
  (`swing/latches/service.py:787-797`) -- **STRICT `<`**, closes not intraday touches, display
  precision on both sides, RD constraint 6, with three existing tests
  (`tests/latches/test_service_terminal.py:37-64`) including "a close exactly at the stop does not
  invalidate". **RD's 2026-08-24 boundary ruling and the shipped code AGREE**, which is worth
  stating: the ruling did not change the encoding, it made the encoding non-negotiable and gave it
  a case (S3.6).
* `_CLEAR_REASON_RANK` = `fill 0, declined 1, superseded 2, invalidation 3, criteria_lapsed 4,
  horizon 5` (`:102-145`).
* `Latch.bars_available` / `bars_through` and `LatchDerivation.archive_status` (per ticker, one of
  `{'ok','unavailable'}`) exist. `swing/latches/models.py:446-448` states the asymmetry this plan
  depends on: **`unavailable` = the read RAISED (our ignorance); `ok` = it completed, so an empty
  map is a FACT about the data.**
* `swing/trades/state.py:28` lists `trade_origin` in the always-required PRESENCE set and **nowhere
  keys a conditional rule on its VALUE** (method: grep `trade_origin` in that file -- one hit). This
  is what makes the seam reordering in S2.2 provably safe.
* `swing/web/routes/trades.py:1040-1075` validates the hidden envelope's `entry_date`,
  `entry_price` and `shares` shapes under a `claimed_auto_fill` consistency gate -- and does **not**
  validate `schwab_order_id`. Read in full; this is the basis of S2.4.1 and EXT-2(b).
* `daily_recommendations` `today_decision` rows exist for every fire the arc touches: OII 169, AMN
  153, RHI 183, CADL 172.
* `latch_order_intents` triggers `trg_loi_no_update` / `trg_loi_no_delete` ABORT every UPDATE and
  DELETE (`0033:834-837`). **A new column on that table could never be back-filled for intent 2** --
  which removes the "link column on `latch_order_intents`" branch of the brief's fork on a
  mechanical fact.

---

## S2. THE DESIGN DECISIONS, OWNED

### S2.1 THE LINK SHAPE -- decision: **a new append-only `latch_order_mandate_links` table, minted by a trigger at acceptance**

My first draft chose "no new table: the acceptance row IS the link". **RD's frozen-value gate
overturns that**, and the reasoning is worth keeping visible because the overturn is instructive.

The acceptance row genuinely IS a durable order<->mandate link: append-only, trigger-protected,
carrying `actual_broker_order_id` and `candidate_id` on one row. What it does **not** carry is the
fire's invalidation, and it can never be made to (S1.10, last bullet). So an implementation built on
it alone must read `candidates.initial_stop` live at comparison time with nothing to check it
against -- which is precisely the shape RD's gate refuses.

**The chosen shape.** One row per broker-accepted latch order, inserted by
`AFTER INSERT ON latch_order_intents WHEN NEW.intent_kind='validity' AND
NEW.validity_outcome='accepted_by_broker' AND NEW.actual_broker_order_id IS NOT NULL`, copying
**exactly TWO values -- the fire's `pivot` and `initial_stop`** -- from `candidates` at that
instant.

> **HARVEST H2 (round 2a, 22A-REV-12), and it was LIVE in the committed plan.** This sentence
> previously read *"copying the fire's `pivot` / `initial_stop` / `zone_cap` from `candidates`"* --
> **a column `candidates` does not have.** Read in full, `0001_phase1_initial.sql:24-41` gives
> `candidates` exactly `close`, `pivot`, `initial_stop` and the criteria/RS fields; there is no
> `zone_cap`. It was a residual of round 1's own AR-14 fix (which REMOVED the stored cap) sitting
> in the very section that defines the schema shape, so an implementer reading top-down would have
> written a DDL that cannot run. The class-sweep after round 1 swept for `frozen_zone_cap` and did
> not sweep for `zone_cap`; **stating the class once is not the same as re-grepping the artifact
> for every spelling of it.** The cap is derived at READ time from the frozen pivot (property 3).

Five properties, each a decision:

1. **A TRIGGER, not a service hook.** A hook in `record_intent` or the route is skippable and
   invisible to a raw INSERT -- the D36 shape. A trigger cannot be bypassed by any writer.
2. **The frozen columns are NULLABLE and the trigger NEVER raises -- enforced by guarded `CASE`,
   not by hope.** `candidates.pivot` / `initial_stop` are unconstrained REAL columns
   (`0001_phase1_initial.sql:24-41`) and `_validate_fire` (`swing/latches/service.py:162-180`)
   proves unusable values are representable and degraded at READ time. My first draft declared the
   trigger would never raise while giving the link table `> 0` CHECKs -- **so a schema-valid
   acceptance on an A+ candidate with a junk price would have aborted the LEDGER write**, the exact
   priority inversion `0036:26-38` forbids. The trigger therefore wraps each copied value in
   `CASE WHEN typeof(x)='real' AND x > 0 THEN x ELSE NULL END`; admission later refuses
   `frozen_value_unavailable`.
3. **NO `frozen_zone_cap` column.** My first draft stored one and then left the SQL-vs-Python
   arithmetic fork OPEN -- a material schema decision a plan must not defer. **Resolved: the cap is
   NOT stored.** It is a pure function of the pivot (`zone_cap_for_pivot`), and it is used ONLY by
   the price-consistency REFUSAL guard (S2.4.1, the FRAMEWORK-CONFORMITY half), never as evidence,
   **and its upper bound passes through `mandate_limit_price` rather than a second `round`**
   (review 22A-R3-05). Computing it at read time from the frozen pivot removes the duplication
   entirely and carries no false "frozen" claim.
4. **NO UNIQUE on `broker_order_id`.** A duplicate would abort the LEDGER write. Cardinality is the
   READER's COUNT (S2.4), per `_bind_the_recommendation` (`cohort_provenance_correction.py:698-731`).
   `UNIQUE(validity_intent_id)` IS declared -- the trigger fires once per row, so it cannot conflict.
5. **`freeze_tier`** in `('live_at_acceptance','pre_barrier_reconstructed')` -- **TWO-valued under
   single-state**; `gap_era_reconstructed` and the era model it names are CARVED to 22-A2 (S12), so
   a pre-barrier reconstruction can never be read as a post-barrier freeze and there is no third
   state to confuse with either.

   > **HISTORICAL, AND KEPT FOR ITS LESSON -- the three-valued enum it describes is CARVED, so the
   > CHECK is two-valued again and correct.** At the time: **THIS LINE AND TWO OTHERS WERE STILL
   > TWO-VALUED (review 22A-R6-03), AND THAT MADE THE THEN-APPROVED DESIGN UNRUNNABLE** -- S4.5C
   > emitted `gap_era_reconstructed`, so a gap-era INSERT would have failed the S4.1 CHECK. **It is the schema-CHECK / Python-constant / dataclass-validator triple failing
   > to land in ONE change** (CLAUDE.md #11) -- I updated the reader, the decline roster and the
   > refusal, and not the CHECK.
   >
   > **AND THREE IS NOT THE SET. Swept by READING every occurrence of `freeze_tier` /
   > `live_at_acceptance` / `LATCH_FREEZE_TIERS` across the plan -- ELEVEN mirror sites, not three:**
   > (1) this prose, (2) the S4.1 table CHECK, (3) the `LATCH_FREEZE_TIERS` frozenset (S4.4),
   > (4) the `__post_init__` validator (S4.4), (5) the repo column mapping (S4.4), (6) the minting
   > trigger's `CASE` (S4.5), (7) the `freeze_tier_for_candidate` reader (S4.5C), (8) rung 9's admit
   > condition (S2.4), (9) `$.freeze_tier` in the evidence schema (S4.3), (10) `AcceptedLatchOrder`'s
   > field (S5.1), (11) the drift test asserting the SQL enum and the Python frozenset agree (S4.4).
   > **Three were stale; the other eight were value-agnostic and survived by luck rather than by
   > design.** The drift test is the only one of the eleven that would have CAUGHT this, and it is
   > the reason it exists.

**A MINTED LINK IS NOT PERMANENT AUTHORITY (review 22A-AR-03, verified).** The ledger deliberately
permits several place/validity cycles, and
`swing/latches/classification.py:493-530 resolve_execution_outcome` takes
`max(children, key=_order_key).validity_outcome` **when it reaches the children at all** --
**CORRECTION (review 22A-R3-04): it returns a matched FILL first (`:515-529`), so "the latest
validity child is authoritative" is NOT universal and my earlier wording overstated a real
code fact.** The latest-child rule governs the validity ladder specifically, so an `accepted_by_broker` row can later be corrected to
`rejected_by_broker` / `not_submitted` / `unknown`. A link minted at the earlier row would persist
and still match. **Admission therefore requires the linked validity row to still be the LATEST
child of its place intent**, established with the SAME `_order_key` the classifier uses -- imported,
never re-spelled (#11). Refusal reason `validity_superseded`, naming the superseding row.

**AND THAT IS NOT SUFFICIENT ORDER AUTHORITY (review 22A-R3-04, verified).** "Latest child of ITS
place" is scoped to one place intent, and the ledger permits SEVERAL place/validity CYCLES on one
mandate: a LATER `place` opens a new cycle while the earlier accepted validity remains the latest
child of its now-obsolete parent, so it passes the rung above unchanged. A pre-fill `cancel` is
ignored entirely -- and `cancel` is a first-class intent kind
(`0033_latch_order_intents.sql:288,346`, read: `place|decline|cancel|attest|validity`). **A stale
envelope can therefore resurrect an obsolete or cancelled order.** Two further rungs, both
refusals, at S2.4c: the linked place must be the GOVERNING place as of the fill, and that broker
order must carry no cancellation at-or-before the fill.

**The second payoff, which is not the point but is real:** on admission the entry path writes
`trades.candidate_id = <fire>`, and `swing/latches/service.py:_match_fill`'s EXACT rung matches on
`entry.candidate_id in draft.candidate_set`. Today OII is linked to its latch at
`fill_link_basis='windowed'` (the heuristic; verified live). After this arc a latched fill links at
`'candidate_id'` from the first derivation. **The arc strengthens the shipped latch panel without
touching it.**

**Rejected: promoting `schwab_order_id` to a `fills` column.** Five-plus existing read sites take
it from the envelope (S10-F3); adding a column creates a second source and a reconciliation arc.

### S2.2 THE ENTRY-PATH SEAM -- decision: **the override is applied AFTER the existing gauntlet, so the LOCK's ordering is provably identical**

My first draft called the resolver FIRST, replacing the `derive_trade_origin` line at `:264`. That
changes what runs before every pre-existing failure branch (missing fields, stop-vs-entry,
duplicate, soft-warn, hard-cap), which is a LOCK claim I could not have proved. **Revised:**

```
# swing/trades/entry.py -- UNCHANGED through the whole existing gauntlet:
derived_origin = derive_trade_origin(conn, req.ticker, req.entry_path)   # :264, untouched
...  validate_for_operation / stop check / duplicate / cap ...           # untouched, same order

# NEW, immediately before the Trade(...) construction and after every existing failure branch:
latched = resolve_latched_provenance(conn, cfg, req)     # declines when cfg is None
if latched.admitted:
    derived_origin      = latched.trade_origin           # 'pipeline_aplus'
    resolved_candidate  = latched.candidate_id
    hypothesis_label    = latched.hypothesis_label
elif latched.recognised_but_underivable:
    derived_origin      = UNSET_TRADE_ORIGIN             # honest NULL; see S2.6.4
    resolved_candidate  = None
```

This is safe because **`trade_origin` is required by the validator only for PRESENCE, never by
value** (S1.10) -- so the validator seeing the pre-override value cannot change any outcome. A test
asserts that property directly rather than trusting the reading.

**AUTHORIZATION AND INSERT MUST BE ATOMIC, AND `with conn:` IS NOT ATOMICITY (review
22A-R15-06, then 22A-R3-01 which showed my R15-06 fix was not one).** The seam above is a
RECOGNITION read; between it and the INSERT another validity child, competing link, hypothesis
transition or trade can land, and the row would be written on a world that no longer holds.

**R3-01's correction, verified in code.** `record_entry`'s transaction is `with conn:`
(`swing/trades/entry.py:441`) -- Python's sqlite3 implicit **DEFERRED** transaction, which acquires
NO write reservation until its first write. Re-running the resolution "inside" it therefore reads
without reserving, and another connection can commit between that read and the INSERT. Demand C
does not do this: it issues an explicit `conn.execute("BEGIN IMMEDIATE")` before authorization and
commits/rolls back itself (`cohort_provenance_correction.py:1764`, read in full, with a
`CallerHeldTransactionError` guard above it at `:1759`). **So does this arc.**

**The rule, in three parts:**

1. **The recognition read stays OUTSIDE**, cheap and query-free when the envelope carries no usable
   order id -- that is what preserves LOCK clause (d).
2. **A write reservation is taken before the authoritative read.** On the latched path
   `record_entry` runs the existing `with conn:` body under an explicit `BEGIN IMMEDIATE` instead
   of the deferred default, following the Demand-C shape verbatim including its caller-held-
   transaction refusal (CLAUDE.md: *the single-transaction service contract -- the function ALWAYS
   owns `BEGIN IMMEDIATE`, and REJECTS a caller-held transaction rather than auto-detecting it*).
3. **The trigger for (2) is "the request carries a usable broker order id", NOT "the recognition
   found a link"** -- R3-01's second hole, and it is the subtler one. A request whose preliminary
   answer was *no link* can acquire a matching validity row before the INSERT and would otherwise
   take the ordinary path on a stale negative. **A negative result is as perishable as a positive
   one**, and the reservation covers both.

A concurrency test mutates the ledger between recognition and INSERT in BOTH directions --
`link -> superseded` and **`no-link -> link`** -- and asserts the written row reflects the INSIDE
verdict each time (cases 21 and 21b).

`record_entry` gains **one keyword-only parameter, `cfg=None`**. Both production call sites already
have `cfg` (`swing/cli.py:790-795`, `swing/web/routes/trades.py:1379-1384`). **That is the entire
signature change in the arc.**

**THE THREE-WAY OUTCOME (review 22A-AR-06/07, and my first draft was self-contradictory here).**
It said a declined resolver always runs the ordinary chain, while case 5 required an
accepted-but-invalidated mandate to land as `manual_off_pipeline`/NULL. Both cannot hold. Resolved:

| outcome | condition | what is written |
|---|---|---|
| **ordinary** | NO recognised accepted link for this fill | today's path, untouched -- **this is the LOCK's scope** |
| **honest unset** | a link IS recognised but admission fails for ANY reason (invalidation, drift, unverifiable coverage, horizon, superseded validity, underivable keys, consumed) | `trade_origin='manual_off_pipeline'`, `candidate_id=None`, **`hypothesis_label=None`**; the ordinary candidate/origin chain is SUPPRESSED |
| **admitted** | link recognised and every guard passes | the three fire-derived keys |

**The label MUST be NULL on the honest-unset path** (22A-AR-07, verified):
`_gate_on_unset_state` (`cohort_provenance_correction.py:675-695`) refuses a trade carrying a
non-NULL label, and `0036:482-492` pins the correction's pre-state label and candidate to JSON
null. Writing the submitted label would make the row **permanently uncorrectable** -- the precise
opposite of the claim my first draft made for it. The submitted value is preserved in a WARNING
log, not on the row.

**THE LOCK, narrowed to what it actually covers and stated so it can be tested.** The brief's
byte-identical guarantee is about **NON-LATCHED fills**, i.e. the ordinary row above:

* (a) For any fill with no recognised accepted link, the persisted `trades` and `fills` rows are
  byte-identical to `main`'s.
* (b) `derive_trade_origin` is called with exactly `(conn, req.ticker, req.entry_path)` and its
  return value is what lands on the row.
* (c) Every pre-existing failure branch raises the same exception type, with the same message, at
  the same point -- **tested with `cfg` PASSED (the production path)**, not only with `cfg=None`.
* (d) When the envelope carries no usable broker order id, the resolver issues **ZERO additional
  database queries**, asserted by counting statements on an instrumented connection.

### S2.3 THE ALIVENESS DISCRIMINATOR -- decision: **delegate the judgment; guard the inputs**

**The probe.** `build_latch_derivation(conn, cfg, horizon_session_override=fill_session,
criteria_lapse_armed_override=False, exclude_trade_ids=frozenset({subject_trade_id}),
strict_decisions=True)`, then **the `Latch` whose `candidate_set` CONTAINS the link's fire** --
**never `identity.candidate_id == fire` (review 22A-R3-06, verified)**. `Latch.candidate_set`
(`swing/latches/models.py:374-377`) is *"the opening fire PLUS every re-confirmation (RD
constraint 4)"*, and the fold keeps the OPENING candidate as the identity, so a same-pivot
RE-CONFIRMATION appears only in the set. An accepted order placed against a reconfirmation fire
would return `fire_not_derivable` under an identity match -- a refusal manufactured by the lookup,
not by the mandate. **Selection is by MEMBERSHIP, with a cardinality check: exactly one latch may
contain the fire**, else `ambiguous_fire_membership`. Case 27 is the reconfirmation case.

**THE EXCLUSION PARAMETER IS NOT OPTIONAL, and its absence made my first draft's live application
unreachable (review 22A-AR-04, verified against the live DB).** On the ENTRY path the subject trade
does not exist yet, so the question is well posed. On the **CORRECTION** path it already does --
and trade 25 has `candidate_id=NULL` with an in-zone pivot fill, which is exactly what
`_match_fill`'s windowed rung admits, giving the fire `clear_reason='fill'` at rank 0. **Verified:
the unexcluded live derivation returns `state=filled clear_reason=fill trade=25 basis=windowed` for
candidate 12284.** So S2.7's probe would have REFUSED the very correction S9 promises. My S0
measurement avoided this only because I excluded the subject trade by monkeypatch and then failed
to carry that exclusion into the design. **EXT-1 therefore carries THREE keyword-only parameters** (`criteria_lapse_armed_override`,
`exclude_trade_ids`, `strict_decisions` -- the third added by review 22A-R15-03; this sentence still
said TWO, review 22A-R7-14),
and the exclusion is scoped to the SUBJECT trade alone -- never to all entries, because the
per-ticker fold uses other fills to resolve supersession and consumption across multiple fires, and
blanking them would change other latches' answers.

#### S2.3.1 What "alive" means

`clear_reason is None` -- **never `state == 'armed'`** (S1.7). **AND NOT `clear_reason is None`
ALONE: the SAME-SESSION TIE in S2.3.1a admits three of the reasons below when their `clear_session`
EQUALS the fill session.** My previous draft's table said *"Every non-`None` reason refuses"* and
kept that sentence after S2.3.1a was written -- **a table falsified by a fix three subsections
later, in the one place an implementer reads to learn the rule** (SELF-SWEEP SS-04).

| `clear_reason` | rank | admit when `clear_session < fill_session`? | admit at the TIE (`clear_session == fill_session`)? |
|---|---|---|---|
| `None` | -- | **YES** (subject to S2.3.2/S2.3.3) | n/a |
| `fill` | 0 | no | **no -- EXPLICITLY excluded from the tie** (another trade's fill is a consumption) |
| `declined` | 1 | no | **YES** (tie; reachable -- `fill_bound = horizon_session`) |
| `superseded` | 2 | no | **YES** (tie; reachable -- fires are scoped `<= horizon_session`) |
| `invalidation` | 3 | no | **YES** at the tie -- fill-wins is UNIFORM (RD, 2026-08-24; the interim carve-out is WITHDRAWN). **Reachable only in principle: `bar_bound` ends the session BEFORE the fill (S2.3.1b/c), so the probe cannot date an invalidation on the fill session, and the ADMIT outcome is delivered structurally as `clear_reason is None`.** |
| `criteria_lapsed` | 4 | **UNREACHABLE** | **UNREACHABLE** -- forced off; S2.3.4 |
| `horizon` | 5 | no | **YES** (tie; reachable -- `horizon_expiry` may equal the fill session) |

**THE `fill` TERMINAL IS WEAKER EVIDENCE THAN IT LOOKS (review 22A-AR-05, and it is the same
heuristic this plan rejects elsewhere).** `_match_fill`'s windowed rung matches ANY NULL-candidate,
same-ticker, in-zone entry -- it never inspects a broker order id. So an unrelated manual fill can
produce `clear_reason='fill'` and a FALSE `mandate_already_consumed` refusal. Two consequences,
both taken: (a) consumption is established AUTHORITATIVELY by the resolver's own
an ORDER-LINKED scan of other trades' entry-fill envelopes (S2.4), not by the terminal; (b) a `fill`
terminal still refuses -- fail-closed -- but the reason NAMES the matched trade and its
`fill_link_basis`, so a heuristic-driven refusal is visible as one rather than presented as proof.

**`horizon` as a refusal is a READING of RD's clause, and the sentence stating it was TRUNCATED
in the committed plan (harvest H3, round 2a 22A-REV-13).** It broke off mid-clause and ran straight
into the next heading, so the argument was absent at its own decision site -- on a point this plan
ROUTES TO RD. Completed here, because a routed question with no stated position is not a routed
question:

> RD's bound says a latch dies at its own INVALIDATION **or above**. `horizon` sits BELOW
> invalidation in the shipped ladder (rank 5, the lowest), so the bound does not name it as a
> killer and the reading is mine, not his. **I refuse on it anyway, and the ground is the mandate,
> not the ladder:** a buy-stop that fills 31 sessions after its fire filled outside the window the
> framework declared for it, so "labels from the fire" would attribute a trade to a mandate whose
> own horizon had closed. The cost of being wrong is a NULL-keyed row the Demand-C surface can
> correct; the cost of being wrong the other way is a silently mis-attributed cohort key, which is
> the defect this arc exists to stop. **Fail-closed, declared, and routed to RD as S11 lists.**

#### S2.3.1a THE SAME-SESSION TIE -- the harvest's largest finding, and the plan had it backwards

**HARVEST H1 (round 2a, 22A-REV-04). It is the single most consequential finding of the whole loop
and no counted round produced it.** The probe excludes the subject trade (S2.3, non-negotiable) and
then tests `clear_reason is None`. **Those two steps together silently DELETE a rule the shipped
ladder has**, and the deletion runs in the FALSE-REFUSAL direction -- the arc minting the very
empty-cohort-key row it was commissioned to stop.

**The shipped rule, read in full rather than paraphrased.** `_Terminal.order_key` is
`(session, _CLEAR_REASON_RANK[reason])` with the docstring *"Earliest date first; rank only on a
tie"* (`swing/latches/service.py:155-160`), `fill` is rank **0** (`:139-146`), and
`_resolve_terminal` ends `if nonfill is None or fill.order_key <= nonfill.order_key: return fill`
(`:838-846`). Its own comment states the semantic outright: *"Rank 0 is what makes a fill dated
exactly ON the winning terminal's session take it -- 'you cannot decline a filled mandate', and the
same for an invalidation or an expiry landing that day."* The ladder's authority is RD's R6 ruling:
*operator FACTS (a fill) beat operator DECISIONS beat framework EVENTS beat framework EVIDENCE of
decay beat DEADLINES* (`:125-128`).

**What the plan was doing.** Remove the subject fill, and a `horizon` / `declined` / `superseded` /
`invalidation` terminal dated exactly ON the fill session becomes unopposed. `clear_reason` is then
non-`None` and the resolver refuses -- **a valid, broker-accepted, order-identified fill dated on
its mandate's own expiry session lands `manual_off_pipeline` + NULL + NULL.** A resting buy-stop
filling on the 30th session of a 30-session window is not exotic; it is the ordinary way a horizon
case resolves. **The probe was asking "would this mandate still be armed if the fill had not
happened?" when the question is "was the mandate alive when it filled?"**

**The rule, and it is the ladder's own, imported rather than re-spelled:**

> **The mandate is ALIVE at the fill when the probe returns `clear_reason is None`, OR when it
> returns a NON-`fill` terminal whose `clear_session` EQUALS the fill session.**

**RD RULED THIS 2026-08-24: APPROVED, UNIFORMLY, INVALIDATION INCLUDED. His interim SESSION-GRAIN
restatement is WITHDRAWN together with the carve-out it created.** He verified the AMN correction
himself, then deliberately re-opened the doctrine **on semantics rather than on the corrected
dates, so it cannot flip on a third arithmetic** -- and concluded that his ORIGINAL bound was right
all along and that the "correction" of it had introduced the error.

**THE GROUND IS A MEASUREMENT ARGUMENT, and it is worth understanding rather than merely encoding:**

> **Refusing same-session collapses is SURVIVORSHIP BIAS in the money cohort.** T4's lesson is that
> losers resolve FAST -- and the fastest loser is the fill that collapses the day it triggers. A
> label rule that ejects exactly those trades **censors H1's left tail and biases its mean UP.** A
> through-the-pivot fill on a live mandate is not a wrong acceptance; it is a true H1 sample whose
> result is ugly. **H1 must own its disasters or its answer is worthless.**

**THE BOUND, FINAL FORM -- the original, with the anchor now pinned:**

> **A latch does not survive its own invalidation** -- the first COMPLETED session whose close
> (strict below, at `PRICE_DP`) breaches the frozen value, **that close belonging to its
> `data_asof` session, NEVER `action_session_date`** -- **and a fill on any LATER session does not
> label from the fire.**

**THE ANCHOR PIN IS THE WHOLE CORRECTION, so it is stated where the bound is and not only in the
post-mortem.** `action_session_date` is FORWARD-looking -- the session a recommendation is FOR --
and a close belongs to `data_asof_date`. Reading a close under the forward anchor is what produced
the off-by-one-session premise this plan corrected (S3.5). **The mechanism is already clean by
construction and S2.3.5 is why:** `derive_latches` judges `DailyBar`s, each carrying its OWN
session, so no run-level stamp ever enters the predicate (#30). **Every synthetic fixture in S3
dates its bars by the `data_asof` session, stated in the fixture.**

#### S2.3.1c THE UNREACHABILITY IS NOT A DEFECT -- IT IS THE MECHANISM

**This subsection previously argued the opposite, and the withdrawal inverts it rather than
deleting it.** Under the carve-out, SS-01's finding -- that the probe's `bar_bound` is
`session_offset(fill_session, -1)` (`swing/latches/reader.py:891`, `:948-950`;
`swing/latches/service.py:786-788`, `:1043-1046`), so **the delegated derivation never loads and
never judges the fill session's own close** -- was a design constraint demanding an explicit second
comparison. **Under fill-wins-uniform it is the implementation.**

Trace it once, because the result is exact rather than approximate:

* A breach on a session STRICTLY BEFORE the fill is inside `bar_bound`, so the probe produces
  `clear_reason='invalidation'` at that earlier date; `(earlier, rank 3)` beats
  `(fill_session, rank 0)` on DATE, and the resolver REFUSES. **That is case 5a, and it is RD's
  bound exactly.**
* A breach ON the fill session is OUTSIDE `bar_bound`, so the probe never sees it and returns
  `clear_reason is None`; the resolver ADMITS. **That is case 5b, and it is fill-wins exactly.**

**So the ladder's own bar bound already encodes RD's bound at the invalidation rung, and the arc
authors NO comparison of its own.** S0(1)'s claim -- *the JUDGMENT already exists; this arc authors
no second invalidation comparison* -- **is restored verbatim, unamended.** The amendment I wrote to
accommodate the carve-out is withdrawn with it.

**EXT-4 IS WITHDRAWN -- MOOT BY DISSOLUTION (CHARC, 2026-08-24).** With no session-inclusive
comparison, nothing ever judges the fill session's own bar, the ladder's probe suffices, and the D6
private-copy fallback dies unborn. **His line, kept because it names a class this project will meet
again:** *an envelope extension that dissolves under a corrected premise was never an extension
request -- it was the premise asking for scaffolding.* **The envelope returns to the three approved
extensions.**

Three notes, each load-bearing:

* **It is a re-derivation of `fill.order_key <= nonfill.order_key` with the subject's own
  `(fill_session, rank 0)` supplied**, so it must be COMPUTED with the imported `_CLEAR_REASON_RANK`
  and `_Terminal.order_key`, never by an inequality written locally (#11 -- and 21-A/21-B's
  comparator-vs-emitter divergence is what a private second copy costs here).
* **`fill` is EXCLUDED from the widening.** A `fill` terminal on the fill session with the subject
  excluded is ANOTHER trade's fill -- a genuine consumption, refused as such (S2.4a), never
  admitted.
* **It cannot widen past the fill session**, because `horizon_session_override=fill_session` bounds
  every walk at-or-before it; the only reachable tie is `clear_session == fill_session`.

#### S2.3.1b WHICH TIE BRANCHES ARE REACHABLE -- `invalidation` is IN THE RULE and UNREACHABLE IN THE PROBE (SELF-SWEEP SS-01)

**The third residual of the H1 fix, and the orchestrator predicted it by name: "assume a third
until you have looked."** The rule covers **all four** non-`fill` terminals -- fill-wins is uniform
(RD, 2026-08-24) -- but **one of the four cannot be CONSTRUCTED through the production probe.**
**The distinction matters and this section exists to keep it:** the rule is not narrowed to three;
the probe simply cannot produce the fourth, and it delivers that branch's correct ADMIT outcome by
a different route (`clear_reason is None`).

Read in full: `build_latch_derivation` sets `derivation_session = session_offset(horizon_session,
-1)` (`swing/latches/reader.py:891`) and loads bars `end=derivation_session` (`:948-950`); the
authoritative `_resolve_terminal` call passes `bar_bound=derivation_session`,
`fill_bound=horizon_session`, `horizon_ref=horizon_session` (`swing/latches/service.py:1043-1046`);
and the invalidation walk runs `_eligible_bars(..., upper=min(bar_bound, horizon_expiry))`
(`:786-788`).

| tie branch | bounded by | reachable at `clear_session == fill_session`? |
|---|---|---|
| `invalidation` | `bar_bound` = **the session BEFORE the fill** | **NO. The probe never sees a bar dated on the fill session, so an invalidation can never carry that date.** |
| `declined` | `fill_bound` = the fill session | YES |
| `superseded` | fires scoped `action_session_date <= horizon_session` | YES |
| `horizon` | `horizon_ref` = the fill session; `horizon_expiry` may equal it | YES |

**Consequence, taken rather than glossed:** the EVIDENCE contract names three reasons (S4.3), while
the RULE names four. **Case 28d (an invalidation dated on the fill session, asserted through the
tie branch) is DELETED -- it could not be constructed, and a case nobody can build is worse than a
missing one because the lens counts it as coverage.** It is replaced by **case 28d', which PINS the
unreachability**: a fixture whose only sub-stop close is dated on the fill session must yield
`clear_reason is None` (the bar is outside `bar_bound`), NOT an invalidation.

**AND UNDER FILL-WINS-UNIFORM THAT PIN IS LOAD-BEARING IN A WAY IT WAS NOT BEFORE.** `clear_reason
is None` is exactly the ADMIT verdict the uniform rule requires for a same-session breach -- **so
28d' now pins the MECHANISM that delivers case 5b, not merely an absence.** If a future change
widens `bar_bound` to include the fill session, 28d' fails, and it fails **loudly on the case that
would otherwise silently start REFUSING 5b and re-introducing the survivorship bias RD's ruling
exists to prevent.** Its docstring says exactly that.

**AND THE SHIPPED DOCSTRING LOOKS LIKE IT CONTRADICTS THIS, SO THE PLAN SAYS WHY IT DOES NOT
(SELF-SWEEP SS-02).** `service.py:766-772` states: *"a mandate whose window closes at S is already
dead for S, so the horizon stays INCLUSIVE at S."* Read alone that refutes the `horizon` branch.
**It does not, because it describes the DRY-RUN PROBE** -- "was this latch live when a fire for
session S arrived?", asked the evening before S, where the subject fill has not happened. **The
AUTHORITATIVE resolution is a different call with `fill_bound = horizon_session`**, so the subject
fill IS counted and rank 0 takes the tie (`:838-846`). An implementer who reads that docstring and
"corrects" the tie rule would re-introduce H1; this paragraph exists to stop that.

**THE EVIDENCE SCHEMA MUST CARRY AN ADMISSION BASIS, OR THIS RULE CANNOT BE AUDITED (review
22A-R4-03 -- a residual of THIS fix, found in the round that reviewed it).** S4.3's citation trigger
requires `$.clear_reason` to be JSON null. A tie-rule admission has a NON-null `clear_reason`, so a
correction admitted through this rule would either ABORT at INSERT or record `clear_reason` null and
**falsely claim an armed probe** -- a false provenance claim minted by the fix that made the
mechanism correct. **The probe evidence therefore carries `$.admission_basis`**, exactly one of:

| basis | `$.clear_reason` | `$.clear_session` |
|---|---|---|
| `armed` | JSON null | JSON null |
| `subject_fill_wins_same_session_tie` | one of `horizon` / `declined` / `superseded` -- **the three the probe can actually date on the fill session (S2.3.1b). `invalidation` is admitted by the RULE (fill-wins is uniform) but is UNREACHABLE HERE by construction, so a row claiming it is incoherent; `fill` is excluded by the rule itself** | REQUIRED, and the trigger asserts it EQUALS `entry_fill_session_date` |

`$.clear_session` becomes a REQUIRED key under both bases (JSON null under `armed`), so its presence
is asserted positively rather than inferred. **Cases 39a-39c:** a tie-basis row with `clear_session`
not equal to the fill session -> REJECTED; a tie-basis row naming `fill` -> REJECTED; an `armed`
row with a non-null `clear_reason` -> REJECTED. **This is also the reason `$.evidence_version`
exists** -- the schema just changed, and a row written under the old shape must be distinguishable
rather than silently re-interpreted.

**This does NOT touch case 5.** Its breach is `2026-08-13` against a `2026-08-17` fill -- STRICTLY
EARLIER, so it refuses exactly as before. The widening is confined to the boundary the shipped
ladder already decides in the fill's favour. **Cases 28a-28c** (horizon, declined and superseded
each dated exactly on the fill session -> ADMIT; the invalidation variant 28d is DELETED as
unconstructable -- S2.3.1b, and this sentence still asserted it, review 22A-R7-13) and **28e** (each dated one session
BEFORE -> REFUSE) are the discriminating pair; an implementation testing bare `clear_reason is
None` passes 28e and fails all THREE of 28a-28c.

#### S2.3.2 The snapshot cross-check (RD's gate, enforced at the comparison)

Before admitting: `round(link.frozen_invalidation, PRICE_DP) == round(latch.latched_initial_stop,
PRICE_DP)`, and the same for the pivot. A mismatch REFUSES with `frozen_value_drift`, naming both
numbers. This is what makes the compared number provably the fire's frozen value (S1.5.3). A NULL
snapshot refuses with `frozen_value_unavailable`.

**THIS COMPARISON IS THE ARC'S SINGLE ROUNDING AUTHORITY, AND NOTHING ELSE MAY RE-PERFORM IT
(review 22A-R8-10).** It happens HERE, in Python, at `PRICE_DP`, once. **The citation trigger does
NOT repeat it**: it binds the RAW operands to their sources by identity and records this
comparison's VERDICT as a datum (`$.invalidation_equal_at_dp` / `$.pivot_equal_at_dp`, with
`$.compare_dp`). **A SQL-side re-comparison is forbidden in both available forms** -- raw equality
is stricter than what the service judged and refuses truthful sub-cent drift, and `round(...,2)` in
SQLite is a DIFFERENT rounding rule from Python's, diverging on 24 measured live `candidates` rows.
The full derivation, the measurement and the declared residual are at **S4.3a**.

#### S2.3.3 The coverage gate -- absence of a breach is NOT proof of no breach

`clear_reason is None` can mean "no bar contradicted the mandate" OR "no bars were available to
judge". `swing/latches/models.py:446-448` distinguishes them (`archive_status`), and
`swing/latches/reader.py:934-947` deliberately permits a derivation with no bars. Admitting on
`clear_reason is None` alone would treat ignorance as evidence.

**The rule.** Let `required_upper = session_offset(fill_session, -1)`.
* If `required_upper < anchor` the judging window is **EMPTY** -- the fill is on the mandate's own
  anchor session, no session has elapsed since the fire, and the mandate is **alive by
  construction.** No bars are required. (This is the common good case -- fire tonight, fill at
  tomorrow's open -- and a naive "require bars" rule would refuse exactly it.)

  > **UNWOUND 2026-08-24 with the carve-out.** Between the carve-out and its withdrawal this bullet
  > said the window was NOT alive by construction and that the fill session's own bar was
  > separately required -- "two windows, two owners". **Nothing judges the fill session's close any
  > more (S2.3.1c), so there is ONE window with ONE owner and the original wording is restored
  > verbatim.** Recorded rather than silently reverted, because a reader of the previous revision
  > should be able to see that the change was withdrawn deliberately and not lost.
* Otherwise require `archive_status[ticker] == 'ok'` **AND per-session completeness**: the loaded
  bars must cover **every NYSE session** in `[anchor, required_upper]`, enumerated with
  `session_offset`, **computed SOLELY from `derivation.archive_closes` and
  `derivation.archive_status` -- the EXACT bars the fold judged
  (`swing/latches/service.py:1362-1375`, `swing/latches/models.py:444-448`) -- and NEVER from a
  second `load_bars_with_status` call.** My previous draft re-read the archive, which review
  22A-R15-04 showed creates a split-world false admission: the parquet is mutable, so the read the
  fold judged could omit a breaching bar while a later read reports complete coverage. One read,
  one world. **`ok` does NOT imply complete** -- `swing/latches/reader.py:930-950` permits an
  empty or partial bar set on a successful read, and `_eligible_bars`
  (`swing/latches/service.py:192-205`) judges only the sessions it was handed. So an `ok` archive
  with a missing INTERIOR session would silently hide a breach. Any gap refuses
  `aliveness_unverifiable`, naming the missing sessions.

  > **A RESIDUAL OF ROUND 2b'S OWN R15-04 FIX, FOUND BY RE-GREPPING THIS SECTION RATHER THAN BY A
  > REVIEWER.** The sentence that stood here said *"Coverage is computed by loading the same window
  > through the same `load_bars_with_status` the derivation uses"* -- **the second read that R15-04
  > deleted, still sitting three sentences below its own deletion, inside the same bullet.** It is
  > removed. The class was stated once and the artifact was not re-swept for it; that is the third
  > time in this loop, and it is why the sweep now greps for the REJECTED mechanism by name rather
  > than for the finding's label.

This is the refusal-only asymmetry the project applies everywhere: an interior hole could hide a
breach, so an unverifiable window must not be read as a survival.

#### S2.3.3b Decision evidence must be PRESENT, not merely absent (review 22A-R15-03)

`swing/latches/reader.py:178 load_decision_intents` returns `{}` on any repo/read/hydration
failure, and its own docstring declines to call the resulting topology conservative. `Latch`
exposes archive status but **no decision-ledger status**, so `clear_reason is None` cannot be
distinguished from *"the decline ledger could not be read"* -- and a `declined` mandate would then
be admitted. My accepted limitation that "declined is covered by `derive_latches`' own tests" was
unsound for exactly this reason: those tests cover the PURE function, not the adapter that feeds
it.

**Fix: EXT-1 gains a third parameter, `strict_decisions: bool = False`.** Under strict mode the
loader RAISES instead of returning `{}`, and the resolver runs strict and converts the raise into
`decision_evidence_unavailable`. A discriminating resolver test injects a loader failure and
asserts non-admission -- it passes trivially under today's silent `{}`.

#### S2.3.4 The `criteria_lapsed` force

RD's bound: a latch never dies of drift. If the flag were armed, `_resolve_terminal` would offer the
lapse to the ladder, and because the ladder resolves EARLIEST-first a lapse at D3 would **MASK** an
invalidation at D5 -- so treating `criteria_lapsed` as "alive" would be blind, not conservative. The
probe therefore forces the rung OFF (EXT-1), and a `criteria_lapsed` reason arriving anyway raises
a typed `LatchProbeInvariantError` rather than taking a branch. S3.7 cases 9 and 10 are the cases.

#### S2.3.4b The as-of rule for DECISIONS, and the ambiguity it refuses (review 22A-R15-05)

`horizon_session_override` scopes fires and bars, **not decisions**.
`swing/latches/classification.py:361 admissible_decisions` filters on `action_session_date` and
never examines `recorded_ts`, while `_order_key` (`:330`) lets a later-recorded row win. Migration
`0033:273-286` draws exactly this distinction: `action_session_date` says WHICH SESSION'S MANDATE,
`recorded_ts` says WHEN THE ANSWER HAPPENED. **So a `place` recorded AFTER the fill can outrank an
earlier `decline` and make a historical probe admit a mandate that was dead when it filled.**

**The rule:** every decision intent the probe would admit for the fire must have
`date(recorded_ts) < fill_session`. Any intent recorded ON the fill session is **UNORDERABLE**
against the fill -- the entry carries only a DATE, and inventing a third clock domain to order them
is what this arc refuses to do -- so it refuses `decision_ordering_ambiguous`. Any intent recorded
AFTER refuses `decision_evidence_post_dates_fill`.

**Clock domain, stated because D37 makes it a live hazard:** `recorded_ts` is naive LOCAL and the
fill session is a DATE. The comparison is therefore date-to-date in ONE domain, deliberately coarse
and deliberately conservative -- it can only refuse. New case 19.

#### S2.3.5 Why `candidates.close` is NOT the bar source

`swing/latches/reader.py:724-745` states it: `evaluation_runs.data_asof_date` is the cohort MAX
while each `candidates.close` is that ticker's OWN last bar, so a lagging ticker is persisted with
an OLDER close under a FRESHER stamp -- gotcha #30, and one of the two 21-A instances CLAUDE.md
records. A predicate on it may raise a MISMATCH but never assert a MATCH, and this predicate must
assert "no breach". `derive_latches` uses `DailyBar`, where each bar carries its own session, so the
delegation is #30-clean by construction and the brief's "no run-level stamp in the predicate" holds.

#### S2.3.6 Cost

The probe rebuilds the derivation (~12 fires, their bars, decision intents, structural verdicts).
Measured interactively: a few seconds. It runs **only after an accepted order matches**, so an
unlatched entry pays nothing (S2.2(d)). What the delegation buys: when the ladder changes, 22-A
inherits it and **cannot silently fail to inherit it** -- the inheritance is a function call, not
the comment #31 warns about.

### S2.4 THE MATCHING PREDICATE

```
SELECT ... FROM latch_order_mandate_links l
  JOIN latch_order_intents v ON v.intent_id = l.validity_intent_id
 WHERE l.broker_order_id = :order_id
```

**Cardinality by COUNT, not `fetchone()`** (S2.1 property 4): `len(rows) != 1` refuses
`ambiguous_accepted_orders` naming the ids. Then the rungs, **each a REFUSAL and each named so a
declined entry says which one fired**:

| # | rung | refusal reason |
|---|---|---|
| 1 | the link's ticker equals `req.ticker` | `ticker_mismatch` |
| 2 | the place parent resolves to a `place` row on the same candidate | `link_parent_incoherent` |
| 3 | **the linked validity row's OWN outcome is `accepted_by_broker`** | `linked_validity_not_accepted` |
| 3b | the linked validity row is still the LATEST validity child of its place intent (`_order_key` imported from `swing/latches/classification.py`) | `validity_superseded` |
| 3c | **every DUPLICATED link field EQUALS its authoritative source** -- `link.broker_order_id` = `validity.actual_broker_order_id`, `link.actual_quantity` = `validity.actual_quantity`, and `link.ticker` / `evaluation_run_id` / `detection_date` = the CANDIDATE's own (review 22A-R7-04) | `link_field_unbound` |
| 4 | **the linked place is the GOVERNING place cycle as of the fill** (S2.4c) | `place_cycle_superseded` |
| 5 | **no cancellation of this broker order at-or-before the fill** (S2.4c) | `order_cancelled` / `cancel_ordering_ambiguous` |
| 6 | **no other trade has consumed THIS ORDER** (S2.4a) | `mandate_already_consumed` |
| 7 | **consumption evidence is INTACT for every fill it must scan** (S2.4a) | `consumption_evidence_unavailable` |
| 8 | **exactly ONE competitor-free accepted link on this TICKER** (S2.4b) | `ambiguous_ticker_orders` / `competitor_liveness_unverifiable` |
| 9 | **the link's STORED `freeze_tier` is `live_at_acceptance`, AND both barrier triggers exist at READ time** (S2.4d, S2.4d.1) | `pre_barrier_unproven` / `barrier_not_installed` |

**THE LINK DUPLICATES; RUNG 3c BINDS THE DUPLICATES BACK (review 22A-R7-04).** The link table copies
`broker_order_id`, `actual_quantity`, `ticker`, `evaluation_run_id` and `detection_date` from rows
that already hold them authoritatively (`0033:291`, `:464`) -- and rungs 1-3b checked ticker, parent
and outcome while **never binding the copies to their sources.** So **a RAW link could cite a
GENUINE accepted validity row while substituting a different broker order id or an inflated
quantity**, and the submitted envelope would then match the forgery rather than the acceptance.
Raw links are treated as reachable throughout this plan -- case 4d(i) plants one -- so
schema-prevention does not cover it. **The same bindings are mirrored in the S4.3 citation trigger**
(a correction may not cite a link whose fields disagree with their sources), and **cases 47a-47c**
plant a substituted order id, an inflated quantity, and a mismatched ticker respectively.

**ELEVEN rungs, counted from the table above: 1, 2, 3, 3b, 3c, 4, 5, 6, 7, 8, 9** -- and **rung 9
changed MEANING TWICE on 2026-08-24 without ever changing its number**, which is why every claim
about it has to be re-read rather than remembered: R6-02 widened it to compute continuity over
`[fire_session, now]`, and **the Option-C carve then reduced it to the STORED TIER plus a
read-time barrier-existence check** (S2.4d). Its refusal reasons moved with it -- `gap_era_unproven`
left with the era model and is **not** a member of the S5.1 roster; `barrier_not_installed` arrived
with CHARC's requirement and **is**. **Rung 3 was
described in prose two sections later and was NEVER IN THE
LADDER (review 22A-R5-07).** S2.4's closing paragraph called `validity_outcome='accepted_by_broker'`
*"the two-tier admission gate"*, and case 4d(i) deliberately plants a `rejected_by_broker` row with
a raw-INSERT link -- but the numbered rung list, the function assignment and the decline-reason
roster all omitted it. `0033:372-377` forbids a NON-accepted validity row from carrying an
`actual_broker_order_id`, which is why this never bites through the SERVICE -- **but the link table
permits a raw link to cite a rejected row, which is precisely the shape case 4d(i) exists to
create, so schema-prevention does not cover it.** An implementer following the ladder literally
would have admitted the planted row, or invented a reason name. **The roster becomes THIRTY-THREE** (this reason plus `quantity_exceeds_order` from review 22A-R5-04)
and case 4d(i) asserts `linked_validity_not_accepted` by name rather than merely "declines".

Rung 9 is RD's refuse-by-default, encoded as an ordinary rung rather than as a special case, so it
cannot be forgotten at one call site and honoured at another.

#### S2.4d RUNG 9 UNDER SINGLE-STATE -- the stored tier PLUS a read-time EXISTENCE CHECK

**CARVED 2026-08-24 (Option C).** The `[fire_session, read]` continuity interval, the era model and
their triggers are DEFERRED to **22-A2** with their findings and rulings intact (S12). What remains
is the reduced rung the commission actually needs.

**The epoch is SINGLE-STATE: one row, one boundary, no eras.** A fire is either at-or-below the
boundary (**pre-barrier**) or above it (**post-barrier**). Rung 9 admits only the post-barrier tier
-- **there is no tier-2 escape in this arc** (RD's refuse-by-default, taken at its word).

| link's `freeze_tier` | rung 9 |
|---|---|
| `live_at_acceptance` | ADMIT, **subject to the existence check below** |
| `pre_barrier_reconstructed` | **REFUSE `pre_barrier_unproven`** -- outright, no evidence path |

##### S2.4d.1 THE BARRIER-INTEGRITY CHECK -- THE BODY, NEVER THE NAME (CHARC's requirement, 2026-08-24, as AMENDED by his ruling on review 22A-R9-01)

He asked whether single-state survives his own CONDITION 3 -- reversibility, with any drop RECORDED
-- and answered yes, **provided the drop's consequence is MECHANICAL rather than procedural**:

> **THE ADMISSION READER VERIFIES THE BARRIER TRIGGERS EXIST AT READ TIME AND REFUSES STRUCTURAL
> ADMISSION IF THEY ARE ABSENT.**

> ### **A NAME CHECK IS NOT AN INTEGRITY CHECK, AND THE HOLE WAS IN THE REQUIREMENT RATHER THAN IN
> ITS ENCODING (review 22A-R9-01; CHARC ruled the repair and owned the origin).**
>
> The previous encoding was `SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name IN
> (...)`. **It checks two NAMES.** It does not check `tbl_name`, the event, the timing, or the
> body -- so **dropping the real barriers and re-creating same-name NO-OP triggers returns 2 while
> `candidates` is fully mutable**, and rung 9 then stamps a mutable candidate structurally proven
> and admits it. **Cases 50a-50c only ever REMOVED trigger names, so every one of them passes that
> fail-open implementation.**
>
> **HIS RULED REPAIR, and it names an existing precedent rather than inventing a shape:**
>
> > **The admission reader compares the trigger BODY, not the NAME** -- `sqlite_master.sql` for each
> > barrier trigger against a **VERBATIM PINNED COPY** of the canonical DDL. **This is the T1b
> > pattern this repo already runs** for schwabdev's private table (the DDL-drift guard that
> > introspects the live schema against a pinned copy).
>
> **The precedent, so the executor copies rather than improvises:** `swing/integrations/schwab/
> auth.py:1519` holds `_V3_SCHWABDEV_DDL`, *"Verbatim copy of the installed schwabdev 3.0.5 private
> DDL,"* and its guard *"introspects the LIVE installed table against this copy and fails loudly on
> a future 3.x private-schema change"* (`:1514-1518`). **Same shape here, one difference that
> matters: T1b's comparison lives in a TEST, and this one lives in the READER**, because the
> property is needed at every admission rather than once at CI.

**THE CHECK.** `swing/data/repos/candidates_immutability_epoch.py` owns a module-level
`_CANDIDATES_BARRIER_DDL: dict[str, str]` -- the verbatim canonical `CREATE TRIGGER` text for
`trg_candidates_no_update` and `trg_candidates_no_delete`, byte-for-byte as migration `0037`
writes them. The reader then:

```sql
SELECT name, tbl_name, sql FROM sqlite_master
 WHERE type = 'trigger'
   AND name IN ('trg_candidates_no_update', 'trg_candidates_no_delete');
```

and for EACH of the two: the row must exist, `tbl_name` must be `'candidates'`, and
**`normalize(sql)` must EQUAL `normalize(pinned)`**.

> **NORMALIZATION IS WHITESPACE ONLY, AND THAT BOUND IS THE RULING'S (CHARC, verbatim):**
> **byte comparison after whitespace normalization ONLY. NO semantic-equivalence judgments.**
> `normalize` collapses runs of whitespace to a single space and strips leading/trailing space.
> **It does NOT lower-case, re-order, parse SQL, or decide that two different bodies "mean the
> same thing."** *A comparator that judges equivalence is a NEW FREE DIMENSION -- and a free
> dimension doing silent work is the defect class this arc has spent nine rounds on (S3.8).* A
> body that differs only in whitespace is the same barrier; a body that differs any other way is
> **not this barrier**, and the reader does not get to have an opinion about it.

**Any mismatch, on either trigger, for any of the three properties -- REFUSE
`barrier_not_installed`, for EVERY candidate, pre- or post-barrier.** The reason name is unchanged
(it is already in the 33-member roster) and it now covers absent-OR-altered rather than absent
alone. **"Single-state" therefore means armed, and verifiably armed with THE ACTUAL BARRIER, NOW.**

**THE DISCRIMINATOR HIS OWN RULE DEMANDS.** *"A body check never exercised against a wrong body is
the existence check wearing better clothes."* So the case set grows from three to five:

| case | fixture | required |
|---|---|---|
| **50a** | both triggers canonical, post-barrier fire | **ADMIT** |
| **50b** | `trg_candidates_no_update` DROPPED | REFUSE `barrier_not_installed` **even for a post-barrier fire** |
| **50c** | both DROPPED | same refusal |
| **50d** | **NEW -- the ruled discriminator.** Drop `trg_candidates_no_update` and re-create a **SAME-NAME NO-OP** trigger (`BEGIN SELECT 1; END`) on the same table | **REFUSE `barrier_not_installed`.** *A name-only implementation ADMITS -- it counts two -- and passes 50a, 50b and 50c* |
| **50e** | **NEW.** A same-name, same-body trigger re-created on a **DIFFERENT table**, and separately one whose body differs ONLY by added whitespace/newlines | the wrong-`tbl_name` variant **REFUSES**; the whitespace-only variant **ADMITS** *(this is the case that pins the normalization bound in BOTH directions -- a stricter byte-equality implementation fails the second half, and a semantic comparator is not needed to pass it)* |

**Why the reader and not a test.** A CI-time guard proves the barrier was canonical when CI ran; the
claim rung 9 makes is about **this admission, now**. The two are different properties, and only the
second one is load-bearing for a structural proof.

**Why this is the load-bearing half and not a belt.** Without it, the stored tier is a claim about
the past that nothing re-checks, and an operator who drops the triggers in an emergency leaves
admission running on a guarantee that no longer exists. **The check converts "any drop is recorded"
from something a person must remember into a consequence nobody can avoid:** dropping the barrier
mechanically halts structural admission. **The emergency DROP escape-hatch survives; what it can no
longer do is leave admission running on a claim the barrier no longer backs.**

**It lives in THE ONE READER** (S4.5C) -- `freeze_tier_for_candidate` returns the tier AND the
existence verdict, so no call site performs its own `sqlite_master` query. **Cases 50a-50c:**
(a) both triggers present, post-barrier fire -> ADMIT; (b) `trg_candidates_no_update` dropped ->
**REFUSE `barrier_not_installed`, even for a post-barrier fire**; (c) both dropped -> same refusal.
**An implementation reading only the stored tier passes (a) and fails (b) and (c).**

**AND IT DISSOLVES TWO ROUTED TRIGGERS.** R5-01's third trigger and R7-02's fourth exist to protect
ERA SEQUENCES -- a lower re-arm after a retirement, an out-of-order `epoch_id`. **Single-state models
no eras, so neither sequence is representable here.** Both holes are REAL and both rulings travel to
22-A2 (S12). **The CRITICAL that was routed to CHARC resolves by DISSOLUTION rather than by a
fourth trigger** -- the fifth dissolution on this arc.


#### S2.4a CONSUMPTION -- and the evidence for it is DESTRUCTIBLE (review 22A-R3-02, verified)

Consumption is established by scanning other trades' entry-fill envelopes for **this broker order
id**, never by `COUNT(*) FROM trades WHERE candidate_id = ?` (review 22A-R15-07: the ordinary entry
path assigns `candidate_id` from pipeline provenance with no accepted order anywhere near it, so
that count would let an unrelated ordinary trade falsely block the real order-linked fill).

**R3-02 showed that scan is not authoritative even for Schwab-auto fills, and the code confirms
it.** `swing/trades/reconciliation_auto_correct.py`'s supported split-into-partials handler
`DELETE`s the original fill (`:2951`) and rebuilds N replacement `Fill(...)` objects
(`:2988-3008`) that set `fill_id, trade_id, fill_datetime, action, quantity, price, reason,
rule_based, fees, manual_entry_confidence, reconciliation_status, tos_match_id` -- and **neither
`fill_origin` NOR `schwab_source_value_json`.** The original row's SELECT (`:2898-2910`) does not
even read those two columns. So a consumption that began in the supposedly authoritative
representation **disappears**, and the same accepted order can be admitted for a second trade.
That disproves S8-L8's stated reason as written, so L8 is corrected rather than defended.

**Live incidence, measured:** 51 fills, **26** carry a `schwab_source_value_json` envelope and all
26 of those carry a `schwab_order_id` (method: `SELECT COUNT(*) FROM fills` and two `LIKE`
counts on the live DB, read-only). The split handler has not yet run against any of them -- but
this is a SERVICE-prevented, not schema-prevented, argument and a shipped supported path is not
prevention. It is stated with its incidence per the recipe's service-prevention rule and then
CLOSED, not cited-and-converged.

**The fix, in the order of preference the plan actually takes:**

1. **Preserve the identity through the replacement path** -- Task 11a adds `fill_origin` and
   `schwab_source_value_json` to the handler's original-row SELECT and carries both onto every
   replacement `Fill`. This is a two-column change in ONE function, it is the semantically correct
   behaviour independent of this arc (a partial of a Schwab fill is still a Schwab fill), and it is
   **inside the brief's `swing/trades/` envelope**. Its own regression test splits a
   Schwab-envelope fill and asserts each partial still carries the order id.
2. **Refuse where the evidence could have been destroyed and was not repaired** -- rung 7. If any
   candidate consumer fill for this ticker carries `reconciliation_status =
   'reconciled_discrepancy_resolved'` with a NULL `schwab_source_value_json`, the scan cannot prove
   non-consumption and refuses `consumption_evidence_unavailable`. **This rung survives even after
   fix 1**, because fix 1 is forward-only and rows already rebuilt are already blind.

**What is NOT done, and why:** a durable order-to-trade consumption table is the right V2 answer
and it is NEW SCHEMA beyond this arc's commissioned shape. Flagged at S10-F7, declared at L14.

#### S2.4b THE COMPETITOR POPULATION IS THREE-VALUED (review 22A-R3-03)

The competing population is links on the same ticker that are latest-validity-AUTHORITATIVE (a
superseded-to-rejected link is not a competitor), UNCONSUMED, and evaluated for LIVENESS at the
fill session. **My previous draft made that evaluation two-valued -- live or dead -- and EXCLUDED
anything it could not resolve.** That is the exact inversion of this plan's own posture everywhere
else: an unprovable competitor was being read as an absent one, so the selected order could be
admitted while two live mandates may have existed.

**The rule: PROVEN-DEAD, PROVEN-LIVE, or UNPROVABLE, and only PROVEN-DEAD is dropped.**

| competitor state | effect |
|---|---|
| proven DEAD at the fill session (invalidated, horizon-expired, declined, superseded, consumed, rejected) | not a competitor |
| proven LIVE | competitor -> `ambiguous_ticker_orders` |
| **UNPROVABLE** -- archive unavailable or incomplete, decision read failed, snapshot NULL or drifted, fire not derivable | **refuse `competitor_liveness_unverifiable`**, naming the competitor and WHY it could not be resolved |

The refusal names the reason because a guard that says only *"ambiguous"* cannot be acted on.
**Cases 23b-23d** plant each unprovable shape in turn; an implementation that drops unresolved
competitors admits all three.

#### S2.4c THE GOVERNING PLACE CYCLE AND THE CANCELLATION HISTORY (review 22A-R3-04)

**Rung 4 -- governing place.** Among the `place` intents for this mandate admissible as of the fill
(the S2.3.4b as-of rule applies unchanged), the link's `place_intent_id` must be the LATEST. A
later `place` opens a new cycle and RETIRES the earlier order regardless of what the earlier
order's own validity children say. Refusal `place_cycle_superseded`, naming both place ids.

**Rung 5 -- cancellation.** `cancel` is a first-class intent kind (`0033:288`,
`CHECK (intent_kind IN ('place','decline','cancel','attest','validity'))` at `:346`). A `cancel`
whose `date(recorded_ts) < fill_session` refuses `order_cancelled`. **A cancel recorded ON the fill
session refuses `cancel_ordering_ambiguous`** -- the same date-only clock policy S2.3.4b states,
applied to the same class of question, because the entry carries a DATE and inventing a third clock
domain to order a cancel against a fill is precisely what this arc declines to do. A cancel
recorded AFTER the fill is not consulted. **Four cases: 29a** (accepted old cycle + newer place, no
validity -> `place_cycle_superseded`), **29b** (cancelled before fill -> `order_cancelled`), **29c**
(cancel on the fill session -> `cancel_ordering_ambiguous`), **29d** (cancel after the fill ->
ADMIT). 29d is the one that fails an implementation refusing on any cancel at all.

**`validity_outcome='accepted_by_broker'` is RUNG 3** (not free-floating prose -- being prose was
exactly how review 22A-R5-07 found it missing from the ladder, and SELF-SWEEP SS-07 found this
paragraph still stating it as an unattached gate afterwards). `0033`'s own CHECK forbids a
non-accepted validity row from carrying an `actual_broker_order_id` at all -- so against the SERVICE
the rung is belt-and-braces with the schema, and the plan CITES that CHECK rather than assuming it.
**Against a RAW link it is not**, which is why the rung is real and why case 4d(i) plants exactly
that shape. RHI is the fall-through case (S3.4).

#### S2.4.1 The envelope is OPERATOR-SUBMITTED; the ladder is a REFUSAL GUARD; the residual is declared

`schwab_source_value_json` round-trips through the POST as a hidden form field. The route validates
`entry_date`, `entry_price` and `shares` shapes behind a `claimed_auto_fill` gate
(`swing/web/routes/trades.py:1040-1075`) -- **and does not validate `schwab_order_id` at all**.
Until now that was harmless: nothing read it. This arc makes it decide provenance.

**My first draft called the resulting ladder "identity evidence". Review 22A-AR-02 showed that is
circular, and it is right:** `fill_origin` is computed server-side but FROM the same hidden inputs,
so it is not an independent server-stamped fact. **The ladder is DEMOTED to what it actually is --
a set of REFUSAL GUARDS -- and the residual is declared rather than dressed up.**

The guards, each a refusal: `req.fill_origin` in
`{'schwab_auto','schwab_auto_then_operator_corrected'}`; the envelope's `schwab_instrument_symbol`
equals `req.ticker`; **`0 < req.shares <= link.actual_quantity`** -- **NOT equality, which would
refuse a supported partial fill (review 22A-R5-04, verified in code)**: `_resolve_match_quantity`
(`swing/trades/schwab_reconciliation.py:521-542`) returns the SUM OF EXECUTED LEGS precisely because
the order quantity can exceed the filled quantity, `_is_execution_bearing_candidate` (`:475-518`)
admits partial-then-cancelled and partial-then-replaced orders, and `entry_auto_fill`
(`:441-470`) persists that EXECUTION quantity as `shares`, while an accepted validity row records
the ORDER quantity (`0033:455-469`). **A two-share accepted order with one share executed before
cancellation gives `req.shares=1` against `actual_quantity=2` -- a genuine order, a genuine fill,
and my equality rung would have written honest-unset provenance for it, minting the very
empty-cohort-key row this arc exists to stop.** Refusal reason `quantity_exceeds_order` for the
over-quantity direction, which stays a refusal. **Cases 15d-i** (partial: `shares=1`,
`actual_quantity=2` -> ADMIT) and **15d-ii** (over: `shares=3`, `actual_quantity=2` -> REFUSE);
an equality implementation fails 15d-i. And the price rung below. Plus the
per-ticker cardinality rung in S2.4b, which is the one that closes the realistic multi-order case.
EXT-2(b) adds a non-empty-string shape rung at the route.

**THE PRICE RUNG USED THE WRONG BOUND, AND IT IS A CLASS THIS PROJECT HAS ALREADY PAID FOR
(review 22A-R3-05, verified in code).** My previous draft wrote
`round(pivot,2) <= round(req.entry_price,2) <= round(zone_cap_for_pivot(frozen_pivot),2)`.
**`round` is a SECOND rounding rule for a quantity that already has one, and CHARC deleted that
exact second definition on 2026-07-30.** `swing/latches/constants.py:317` `mandate_limit_price` is
*"THE mandate's limit price: the LARGEST WHOLE-CENT PRICE THAT DOES NOT EXCEED THE CAP"* -- it
FLOORS -- and its docstring records the live consequence: on the VSTS cap of `17.407`,
`round(17.407, 2) = 17.41` **EXCEEDS the cap**, so the comparator *"was blessing a price OUTSIDE
the buy zone, which is exactly what the floor ruling exists to prevent"*, and **49.5% of
two-decimal pivots produce a cap whose third decimal is non-zero, so the disagreement is the
ORDINARY case, not an edge.** `swing/latches/orders.py:472-482 _mandate_limit_of` is the standing
enforcement: *"THE ONLY WAY THE COMPARATOR MAY OBTAIN A MANDATE LIMIT (CHARC ruling)."* My draft
re-opened it in a new module.

**The corrected rung, in two halves that check different things:**

* **FRAMEWORK CONFORMITY:** `round(frozen_pivot, PRICE_DP) <= round(req.entry_price, PRICE_DP) <=
  mandate_limit_price(zone_cap_for_pivot(frozen_pivot))`. The upper bound comes from
  `mandate_limit_price` -- **imported, never re-rounded** -- so the guard admits exactly the prices
  the framework could have emitted an order for.
* **BROKER REALITY:** the accepted validity row records `actual_stop_price` and
  `actual_limit_price` (intent 2: `53.98` / `55.59`, S1.2), and `0033`'s schema permits them to
  diverge from the framework values. **My draft ignored them entirely.** Where both are present,
  `req.entry_price` must ALSO satisfy `round(req.entry_price, PRICE_DP) <=
  round(actual_limit_price, PRICE_DP)`: the order the broker actually accepted could not fill above
  its own limit, so a price above it did not come from this order. A divergence between the two
  halves is not itself a refusal -- it is a WARNING naming both -- because the schema permits it;
  what refuses is a fill price outside EITHER bound.

  > **AND THE DECLARED API COULD NOT IMPLEMENT THIS RUNG (review 22A-R8-07 -- a pre-existing
  > design/API mismatch eight rounds had not reached).** `AcceptedLatchOrder` carried
  > `frozen_pivot`, `frozen_invalidation`, `actual_quantity` and `freeze_tier` and **NO
  > `actual_limit_price`** (`0033:331`, `swing/data/models.py:2650`), while
  > `assert_fill_consistent_with_order(order, *, ticker, price, shares, fill_origin)` takes **no
  > connection** and therefore cannot fetch it. **So this guard and its case 30c were
  > unimplementable as specified** -- an executor would have had to widen the signature, open a
  > second connection, or silently drop the rung, and dropping it is the one that looks like
  > success.
  >
  > **THE FIX IS IN THE DATACLASS, NOT THE SIGNATURE (S5.1).** `AcceptedLatchOrder` gains
  > `actual_limit_price: float | None`, populated by `find_accepted_latch_order` from **the JOIN it
  > already performs** -- `JOIN latch_order_intents v ON v.intent_id = l.validity_intent_id`
  > (S2.4), so the column is already in scope and **no new query, no new connection and no
  > signature change is required.** Keeping `assert_fill_consistent_with_order` connection-free is
  > deliberate: it is a PURE function over the order and the submitted envelope, which is what
  > makes it testable without a database and what keeps every envelope guard in one place.
  >
  > **`actual_stop_price` is deliberately NOT carried.** No rung reads it; the WARNING names the
  > two BOUNDS (the framework cap and the accepted limit), not the stop. Stated so the next reader
  > finds a decision rather than an apparent omission -- the same courtesy `bars_through` gets at
  > S4.3.
  >
  > **NULL is the ordinary case and must not refuse.** Of the five live `latch_order_intents` rows
  > exactly one (intent 2) carries `actual_limit_price`; the four `place` rows carry NULL by
  > construction (measured). The rung is therefore **conditional -- "where both are present"** --
  > and **case 30d** pins it: an accepted link whose `actual_limit_price` is NULL admits on the
  > framework bound alone. An implementation treating NULL as zero, or as a refusal, fails it.

**Cases 30a-30d:** (a) a frozen pivot whose cap's third decimal is non-zero (the `17.407` geometry
scaled onto the fixture) with a fill at the `round`-up cent -> **REFUSE**; a `round`-based
implementation ADMITS, and this is the case that fails it. (b) the same fixture with a fill at the
floored cent -> ADMIT. (c) `actual_limit_price` set BELOW the framework cap with a fill between the
two -> REFUSE, plus the divergence WARNING; an implementation ignoring the validity row's actuals
admits. **(d) `actual_limit_price` NULL -> ADMIT on the framework bound alone** (review 22A-R8-07):
NULL is the ordinary shape for four of the five live intent rows, and an implementation that
refuses on it, or coerces it to `0.0`, refuses every fill.

**The residual, stated with its threat model (S8-L10):** a single-operator local application with
no adversary. The realistic failure is a STALE or MIS-COPIED envelope, and every guard above must
agree for it to pass -- same ticker, same quantity, price inside that specific mandate's frozen
zone, and no second accepted order on the ticker. **What still gets through: an envelope naming a
DIFFERENT accepted order for the SAME ticker whose zone and quantity coincide, in a window where
the cardinality rung sees only one live order.** The V2 fix is a server-side nonce binding the
rendered envelope to the POST, or a POST-time Schwab re-fetch; both are web-layer arcs outside this
envelope. **Flagged for CHARC/RD rather than absorbed.**

#### S2.4.2 The fill session is `req.entry_date`

Already validated date-only at `entry.py:290-300`, and it is the OPERATOR-CORRECTED date where a
correction exists. Reading the date from the envelope instead would probe the wrong session. The
resolver also refuses unless `is_trading_session(fill_session)` -- a non-session anchor would make
`session_offset` walk from a weekend and silently shift the probe. **Case 41b is the case; my
previous draft cited S3.5c, which is the corrected-DATE discriminator and never supplies a
non-session anchor at all** (SELF-SWEEP SS-10 -- a MIS-CITED case reads exactly like a covered one,
and only a read tells them apart).

### S2.5 PRECEDENCE vs THE `pattern_evaluations` CHAIN

1. Latch admits -> `candidate_id` = the fire; the PE chain is not consulted for `candidate_id`.
   `trades.pattern_evaluation_id` is still persisted from the request (a different backlink, not
   this arc's).
2. **NO recognised link** -> the existing chain runs unchanged, in its existing order and gating.
   **A RECOGNISED link that is then refused does NOT run it** -- it takes the honest-unset path
   (S2.2), writing `manual_off_pipeline` + NULL candidate + NULL label. My previous draft left this
   sentence saying "latch declines", which contradicted S2.2 and case 5 and would have produced
   different persisted values and different correctability depending on which sentence an
   implementer read (review 22A-R15-11).
3. A caller-supplied `req.candidate_id` disagreeing with an admitted latch -> the latch wins,
   WARNING logs both. Unreachable in production (S1.6).
4. Latch-derived and PE-chain candidates would have disagreed -> WARNING logs both and the
   resolution. Diagnostic only.

### S2.6 THE THREE COHORT KEYS MOVE TOGETHER

`provenance_corrections.corrected_fields_json` requires exactly the three fields in order, and
Demand C's `_gate_on_unset_state` refuses a trade already carrying ANY of them. An entry path
writing origin + candidate but leaving the label NULL would mint rows that are incoherent AND
permanently uncorrectable. Relaxing that gate is unavailable: the schema pins
`pre_value_json."trades.trade_origin" = 'manual_off_pipeline'` in a table-level CHECK, and changing
one means rebuilding the audit table of record.

**On admission the entry path writes all three, or it admits nothing.**

#### S2.6.5 THE BARRIER DOES NOT FREEZE THE LABEL'S INPUTS (review 22A-R3-09, corroborated by the harvest's 22A-REV-05)

`candidate_criteria` is a SEPARATE table (`0001_phase1_initial.sql:47-55`, read in full) with
`candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE` and NO barrier of its
own. `swing/data/repos/candidates.py:180 fetch_candidate_by_id` hydrates it live, and **its own
docstring says why that matters**: *"The criteria are not decoration here: the hypothesis label is
built from the non-pass criterion set, so an unhydrated row would silently produce a DIFFERENT
(cleaner) label than the framework's own record supports."*

**So the pivot/stop cross-check can stay perfectly clean while the derived LABEL moves**, and this
plan may NOT claim in general that the persisted label is the fire's contemporaneous label. Three
things follow, and the plan takes all three:

1. **The claim is narrowed, at every site that made it.** "Labels from the fire" means the label
   the framework's CURRENT record of that fire supports. The pivot and stop are frozen
   structurally from 0037; the failed-criteria SUFFIX is not.
2. **The derived label and its criteria basis are recorded ON THE CORRECTION PATH ONLY, and my
   previous draft overstated this (review 22A-R4-04).** I wrote that they are "RECORDED at
   admission", full stop. **On the ENTRY path nothing durable receives them:**
   `LatchedProvenance.probe_evidence` is an in-memory return value, `record_entry` persists the
   three trade keys and the submitted fill envelope and nothing else (`swing/trades/entry.py`
   through the `Trade(...)` construction and the fill insert), and the link table stores only pivot
   and stop. So on the entry path **there is no detection either** -- only a WARNING log, which is
   not a record. **The claim is narrowed to the correction path**, where
   `cited_latch_probe_json` genuinely persists it, and **L13 states the entry-path gap in those
   words.** The alternative -- a durable entry-time provenance row -- is NEW SCHEMA (S10-F6/F7) and
   is not smuggled in here; **case 31 is scoped to the CORRECTION path accordingly**, reading the
   persisted evidence back and comparing it against the mutated criteria.
3. **Freezing `candidate_criteria` is the real fix and it is ROUTED, not taken** (S4.5B): two more
   `CREATE TRIGGER`s on a THIRD table, beyond CHARC's CONDITION 4 enumeration. **Note the DELETE
   half is already half-closed by accident:** `ON DELETE CASCADE` from `candidates` cannot fire
   once the `candidates` DELETE barrier exists, so the remaining exposure is a DIRECT
   `UPDATE`/`DELETE`/late-`INSERT` on `candidate_criteria` itself.

**Case 31:** mint a link, then UPDATE a criterion row between minting and admission; the pivot/stop
cross-check passes and the derived label CHANGES. **The case asserts the change is VISIBLE in the
recorded evidence** -- it does not assert a refusal, because with the barrier declined there is
nothing to refuse on. **This is a case that pins a LIMITATION rather than a guarantee, and it is
labelled as one in its own docstring** so nobody later reads its green as proof the label is
frozen. **L13** carries it.

#### S2.6.1 The label comes from ONE derivation, shared with Demand C

Task 5 extracts rungs 16-18 of `cohort_provenance_correction._derive` -- the persistence bound, the
AS-OF registry, the clock-margin guard, the matcher, and `canonicalize_hypothesis_label` -- into
`derive_cohort_keys_for_fire(conn, *, candidate_id)`, and `_derive` calls it. **Behaviour-preserving**,
pinned by the whole existing Demand-C suite staying green unchanged plus a golden test reproducing
the live CADL correction (candidate 12341 -> `'A+ baseline (aplus); failed: TT8_rs_rank'`,
hypothesis 1, history row 1, read off `provenance_corrections` row 1). If it cannot be made
behaviour-preserving, Task 5 STOPS and routes.

#### S2.6.2 `derivation_rule_version` follows the extraction

`DERIVATION_RULE_SOURCE_SHA256` pins the derivation source; moving code changes what it covers.
Task 5 re-derives the pin and bumps `DERIVATION_RULE_VERSION` / `DERIVATION_RULE_DEPENDENCIES` per
that module's own contract, updating the pin test in the SAME commit (#11 applied to a source
hash). Correction row 1 keeps `'2026-08-13.3'`; the drift reader compares against the stored value.
**Highest-risk item in the arc, called out so review looks at it.**

#### S2.6.3 The operator's submitted label

On admission the derived label replaces `req.hypothesis_label`. Refusing the entry instead would
invert the priority `0036:26-38` establishes (cohort bookkeeping must not block a money-bearing
operation). V1: write the derived label and `log.warning` naming trade, ticker, order id, submitted
and derived labels. EXT-3 would make the form prefill latch-aware so the substitution is a no-op
and visible beforehand. S8-L4 declares the residual.

#### S2.6.4 Every recognised-but-refused outcome takes the honest-unset path

Generalised into the three-way table in S2.2, which my first draft applied only to
`keys_not_derivable`. **Any** recognised link that fails admission -- invalidation, frozen-value
drift, unverifiable coverage, horizon, superseded validity, consumption, underivable keys --
suppresses the ordinary candidate/origin chain and writes `manual_off_pipeline` + NULL candidate +
**NULL label**.

**Why suppression rather than fallback:** for a ticker that is `aplus` in today's latest run, the
ordinary chain would write `pipeline_aplus` plus TODAY's candidate -- a different candidate from
the mandate we know this fill came from. Silent-wrong, not honest-NULL, and exactly what RD's
trade-25 standard forbids. **The test must seed a CURRENT `aplus` run for the ticker**, or it
cannot distinguish suppression from plain fallback (S3.7 case 12).

### S2.7 THE DEMAND-C EXTENSION -- replace ONE guard, automatically, with the tier recorded

* Resolve the trade's authoritative entry fill through the module's existing
  `resolve_authoritative_entry_fill` (which already honours D38 S3.0: load unfiltered, validate
  every timestamp, order in Python), read its `schwab_source_value_json`, and run the SAME matching
  predicate as S2.4 plus the SAME probe as S2.3 -- **with `exclude_trade_ids={subject}`, without
  which the probe sees the subject's own fill and refuses (S2.3, verified)**.
* **Match found:** tier `latch_ladder`. The cited candidate MUST equal the link's fire, else REFUSE
  naming the fire. The probe must admit, else REFUSE naming `clear_reason` and `clear_session`. The
  last-word guard is NOT run.
* **Match found on a PRE-BARRIER link: REFUSE `pre_barrier_unproven`, OUTRIGHT.** There is no
  evidence path in this arc.

  > **CARVED TO 22-A2 FROM HERE (Option C, 2026-08-24):** RD's tier-2 evidence class and its
  > four-part binary conjunction * the attestation semantics (`descendant_count`,
  > `anchor_strength`, `evaluated_at`, `verification_method`, the resolved remote SHA) * the
  > preflight/transaction boundary that keeps a network call out of `BEGIN IMMEDIATE` * the replay
  > contract and context-drift-is-not-divergence * the `--frozen-value-evidence` CLI option * and
  > **trade 25's correction.** All of it is preserved verbatim-liftable at **S12**, **AS RULED
  > rather than as questions** (RD's binding condition), together with the ten findings rounds 6-8
  > raised against it. **Nothing in the reduced arc reads any of it**, and the existing five-option
  > CLI manifest pin stays GREEN.
  >
  > **THE CONSEQUENCE, STATED AS A COST:** the correction surface in this arc corrects **no
  > pre-barrier trade**, which is every trade that exists today. **Trade 25 keeps a pending-label
  > row that governs every monthly read until 22-A2 lands -- tolerable for one read, increasingly
  > costly after, and 22-A2 should land BEFORE THE OCTOBER READ if trade 25 has closed by then**
  > (RD, 2026-08-24).

* **Citation-shopping is closed harder, not reopened:** under the latch ladder the operator cannot
  choose among candidates -- the citation is FORCED to the fire named by an append-only row the
  broker's acceptance created. The last-word guard prevents shopping by ranking; the latch ladder
  prevents it by leaving nothing to rank.
* **NO NEW CLI OPTION, AND THE FIVE-OPTION MANIFEST PIN STAYS GREEN.** *(This bullet previously
  added `--frozen-value-evidence` and updated the pin five -> six "in the same commit". Both the
  option and the tier it selected are CARVED to 22-A2 -- the banner six lines above says so -- and
  **a task ladder that still updated the pin would have turned a correct green into a false red**:
  the pin's subject did NOT change in this arc.)* Preview and apply PRINT the tier, the order id,
  the two intent ids and the probe verdict. **The TIER is DETECTED from the record and never
  chosen**, which is unchanged and is the property the carve preserves: with one admitting tier,
  there is nothing for an operator to select.
* The scope-boundary framing from brief S2.3 is written verbatim at the dispatch site: the
  last-word guard's refusal of OII's `aplus` citation is CORRECT for what the guard is -- it ranks
  the framework's BUCKET SERIES, and the latch ladder is a different AUTHORITY the guard
  structurally cannot see.

---

## S3. THE ACCEPTANCE TEST

The brief's **six cases are the binding gate** (S3.1-S3.6). S3.7 adds the coverage the six cannot
reach, and **names the clauses that would still have no case** -- because a gate assembled only
from states the ledger holds inherits the ledger's coverage.

All fixtures are built from REAL rows (S1). Each case states the value under the pre-fix path and
under the post-fix path, so no assertion passes under both.

> **RD'S REFUSE-BY-DEFAULT RULING SPLITS EVERY ADMITTING CASE IN TWO, and the plan says so rather
> than quietly picking one (S1.5.3a).** Rung 9 refuses a `pre_barrier_reconstructed` link, and
> **every fire that exists today is pre-barrier** -- so a fixture built from a real row admits only
> in the world the mechanism will actually live in. **The convention, applied uniformly:** an
> admitting case seeds the epoch boundary BELOW its fire so the link mints `live_at_acceptance`,
> and its docstring states that it is testing the POST-BARRIER world. **Each such case then carries
> a `-pre` twin** running the identical fixture with the REAL boundary, asserting
> `pre_barrier_unproven`. Without the twin, an implementation that never wrote rung 9 passes the
> whole suite; with only the twin, the mechanism is never exercised. **Neither half is optional and
> neither substitutes for the other.**
>
> **THE CONVENTION IS SCOPED, AND MY PREVIOUS DRAFT STATED IT UNIVERSALLY (review 22A-R5-09).**
> Stated universally it would once have REVERSED case 32f's required verdict from ADMIT to REFUSE,
> because 32f admitted a genuinely pre-barrier trade on verified tier-2 evidence. *(32f is CARVED,
> so the counterexample is historical -- but the SCOPE it forced is not, and it is why the
> convention is written with a population rather than as a blanket rule.)* **The convention applies
> to exactly one population: resolver cases admitted through ordinary `latch_ladder` authority,
> which is what rung 9 governs.**
> **EXEMPT, RE-DERIVED AFTER THE OPTION-C CARVE:** every raw-INSERT schema case (34a-34g,
> 35a-35c / 35n / 35p, 39a-39c, 48a-48p, 49a-49j) and every ordinary/no-link path case (2, 3, 4,
> 4b, 18) -- none reaches rung 9. *(The tier-2 exemptions are GONE WITH THE MACHINERY rather than
> exempt: 1-tier2, 32a-32k, 40a-40f and 46a-46c no longer exist in this arc.)*
>
> **THE TWINNED SET -- AND THE LIST IS NO LONGER THE INSTRUMENT (review 22A-R8-09).** It had gone
> stale THREE times, most recently when case 5b flipped to ADMIT and acquired no `5b-pre`. **The
> fix for the third staleness then produced a FOURTH: the set was written out twice, on adjacent
> lines, one copy carrying `5b` and one not** -- two rosters disagreeing inside the block that
> exists to state one. That is the recipe's roster lesson exactly: *when a fix's shape is "maintain
> a list," the fix is not the list.*
>
> **THE CLOSURE CHECK IS THE MECHANISM. THE LIST BELOW IS ITS CURRENT OUTPUT, AND IS NOT
> AUTHORITATIVE.** A test collects every acceptance case whose **expected RESOLVER outcome is
> `admitted=True` reached through ordinary `latch_ladder` authority**, and asserts each has a
> `-pre` twin. It fails on the day a new admitting case lands without one -- which is the only
> property that keeps this true, since every hand pass so far has been followed by another hand
> pass.
>
> **THE CRITERION IS STATED PRECISELY, because three of this roster's four failures were boundary
> disputes rather than oversights:** the collector keys on the case's declared resolver verdict.
> **IN:** resolver cases expecting `admitted=True`. **OUT, each for a stated reason** -- raw-INSERT
> schema cases (34a-34g, 35a-35c, 39a-39c, 48a-48p, 49a-49j: they never reach rung 9); ordinary /
> no-link path cases (2, 3, 4, 4b, 18: no link, so no tier); refusing and
> recognised-but-underivable cases (5a, 5c, 7, 7b, 9, 9b, 11b, 11c, 12, 13, 14, 15a-15e, 15d-ii,
> 15f, 16, 19, 20, 22b, 23b-23d, 29a-29c, 30a, 30c, 41a-41e, 50b, 50c); and **PROBE-LEVEL cases
> that assert a probe field rather than a resolver verdict -- case 28d' is the named example**, and
> naming it is the point, because it is the one a reader would otherwise argue about every time.
>
> **Current output of the check -- SEVENTEEN cases, counted item by item rather than estimated**
> *(I wrote "16" here on the first pass and the count was wrong: the roster's fifth failure in
> one loop, in the paragraph replacing the roster with a check, which is the best argument for
> the check that this section could carry):*
> **1, 4c-i, 5b, 6, 8, 10, 15d-i, 22, 23, 24, 27, 28a, 28b, 28c, 29d, 30b, 30d** -- with **`5b-pre`
> NEWLY WRITTEN (S3.5)** and **`30d-pre` NEW with case 30d itself** (review 22A-R8-07's NULL
> `actual_limit_price` admission). Case **28d is gone** (S2.3.1b: unconstructable).

### S3.1 CASE 1 -- OII (trade 25, LIVE): validated latch, bucket drifted, invalidation never approached, fill at the frozen pivot -> **labels from the fire**

Fixture: fire candidate 12284 (`aplus`, session `2026-08-10`, pivot `53.97999954223633`, stop
`41.41999816894531`, close `47.970001220703125`); the later `watch` rows 12402/12478/12555/12642 and
the 08-18 `skip` row 12722 present, **so bucket drift is real in the fixture**; archive closes
`2026-08-10..2026-08-14` = `51.12, 50.76, 51.02, 51.35, 52.20`; intents 1 and 2 verbatim; the link
row minted by the trigger; envelope `schwab_order_id='1007523377009'`,
`schwab_instrument_symbol='OII'`; `fill_origin='schwab_auto'`; `req.entry_date='2026-08-17'`, price
`53.98`, shares `2`.

* **PRE-FIX:** `trade_origin='manual_off_pipeline'`, `candidate_id=None`, `hypothesis_label=None`
  -- **MEASURED off trade 25's live row**, not assumed (`SELECT id, candidate_id, trade_origin,
  hypothesis_label FROM trades WHERE id=25` -> `(25,'OII',None,'manual_off_pipeline',None,...)`).
  My previous draft wrote "label as submitted" here, which is only accidentally the same thing.
* **POST-FIX:** `trade_origin='pipeline_aplus'`, `candidate_id=12284`,
  `hypothesis_label='A+ baseline (aplus)'` -- the string MEASURED in S1.8, not invented.
* Resolution names `validity_intent_id=2`, `place_intent_id=1`, `broker_order_id='1007523377009'`,
  `clear_reason=None`, **`bars_through='2026-08-14'` and `horizon_session='2026-08-17'`** (the two
  fields review 22A-R5-02 split apart -- naming one `probe_session` gave it two incompatible
  definitions), `freeze_tier`, and the snapshot equality.
* **Drift-is-not-death asserted directly:** a variant with the 08-17 `watch` row REMOVED must give
  an identical result. If it changes, something is reading the bucket series.
* **CASE 1 runs in the POST-BARRIER world** (epoch boundary seeded below 12284) -- it is the case
  the brief makes binding, and it asserts the ladder reaches the fire.
* **CASE 1-pre (RD's ruling):** the identical fixture with the real boundary -> NOT admitted,
  decline reason **`pre_barrier_unproven`**, row lands `manual_off_pipeline` + NULL + NULL. **This
  is what the live entry path does on 12284 the day 0037 lands**, and S9 does not pretend
  otherwise.
> **CASE 1-tier2 IS CARVED TO 22-A2 (Option C).** It admitted trade 25 on tier-2 evidence, and
> there is no tier-2 in this arc. **CASE 1-pre is therefore no longer a "twin" -- it is trade 25's
> LIVE outcome under 22-A**: `pre_barrier_unproven`, keys honestly NULL, pending-label row intact
> until 22-A2 lands (RD's October marker, S1.5.3a).

### S3.2 CASE 2 -- AMN (trade 20, LIVE): NO latch rows -> falls through. **The no-latch fallback control**

Fixture: fire candidate 11926 (`aplus`, `2026-08-03`, pivot `36.27000045776367`, stop
`30.850000381469727`); archive closes `2026-08-03..2026-08-06` = `33.00, 33.25, 32.80, 30.80`;
**zero `latch_order_intents` rows and zero link rows**; envelope
`schwab_order_id='1007427919619'` with the operator correction to `2026-08-07`;
`req.entry_date='2026-08-07'`.

* **PRE-FIX** and **POST-FIX** identical: `trade_origin='manual_off_pipeline'`, `candidate_id=None`
  (AMN is `skip` in the 08-07 run).
* **The discriminating assertion is the decline REASON: `no_accepted_latch_order`.** Asserting only
  the origin would pass under almost any broken implementation, because AMN's answer is
  `manual_off_pipeline` either way. **This case cannot test the invalidation clause and the plan
  does not pretend it does** -- that is what the brief's correction established and it is why cases
  5 and 6 exist.

### S3.3 CASE 3 -- VSTS (LIVE): never filled -> nothing

Fixture: fire candidate 11629 (`aplus`, `2026-07-27`, pivot `16.899999618530273`, stop
`13.399999618530273`); latch view events present; **no trade, no fill, no acceptance row, no link
row**. Assertions: no arc code path is entered; no row is written to any table; the latch derivation
for 11629 is byte-identical before and after (compare `dataclasses.asdict` of the derived `Latch`).
This tests that the arc has NO effect where there is no fill -- the class that would show as a
phantom label on an unfilled mandate.

### S3.4 CASE 4 -- RHI (trade 24, LIVE, ITS REAL SHAPE): place-intent WITHOUT a validity row -> falls through

**Built as the real shape, never as "no latch"** (brief S4 case 4, explicit): fire candidate 12442
(`aplus`, `2026-08-13`, pivot `44.18000030517578`, stop `34.77000045776367`); `place` intent 4
present **and no validity row, therefore no link row**; the 08-14 `watch` candidate 12518; trade 24
`candidate_id=12518`, entry `2026-08-14` at `44.20`, shares `3`; envelope
`schwab_order_id='1007574345138'`.

* **PRE-FIX:** `trade_origin='pipeline_watch_manual'`, `candidate_id=12518`,
  `hypothesis_label='Broad-watch baseline (watch); failed: proximity_20ma, tightness'`.
* **POST-FIX: byte-identical**, asserted field by field, with decline reason
  `no_accepted_latch_order`.
* **Discriminates ONE design cleanly** (narrowed again by review 22A-AR-10): keying on an ARMED
  LATCH rather than on an accepted order -- RHI's latch IS armed at its fill session. It does NOT
  discriminate "requires order-id identity" from "requires any accepted link", because RHI has
  NEITHER a validity row nor a link, so both implementations decline it for the same reason. Cases
  4c and 4d below carry those two clauses.
**S3.4b (price-heuristic design).** `candidate_id=NULL`, in-zone price, matching quantity, **no
validity row** -> must decline. Fails an implementation reusing the shipped windowed price
heuristic, which RHI cannot fail because that rung requires `candidate_id IS NULL`.

**S3.4c (order-id identity) -- SPLIT IN TWO, because the single fixture did not discriminate
(review 22A-R15-12).** As written, both links' windows contained the fill, so the correct
implementation refuses on per-ticker cardinality -- and an implementation that IGNORES the
submitted order id but implements the same cardinality rung produces the identical verdict.

* **4c-i (identity, cardinality NOT engaged):** two accepted links on the same ticker, but only
  ONE is live at the fill session (the other is horizon-expired, so it is not a competitor under
  S2.4's population rule). The envelope names the LIVE one -> ADMIT, and assert the admitted fire
  is that order's. Then the same fixture with the envelope naming the DEAD one -> refuse
  `mandate_not_alive`. An implementation ignoring the order id cannot produce both verdicts.
* **4c-ii (cardinality, identity satisfied):** two accepted links BOTH live at the fill session ->
  refuse `ambiguous_ticker_orders` regardless of which the envelope names.

**S3.4d (accepted-outcome gate).** Two shapes: (i) a `rejected_by_broker` validity row with a link
planted by raw INSERT -> decline; (ii) an `accepted_by_broker` row later SUPERSEDED by a
`rejected_by_broker` child of the same place intent -> decline `validity_superseded`. Shape (ii) is
the 22A-AR-03 case and it fails every implementation that reads the linked row's own outcome
instead of the latest child's.

### S3.5 CASE 5 -- SYNTHETIC BREACH: validated latch + breach at the real AMN magnitude -> **NOT from the fire, keys honestly NULL**

**Labelled SYNTHETIC in the test name and docstring**, with the reason stated there: no live case
reaches the invalidation branch, so this case exists to make the branch falsifiable. Bad rows are
planted by **raw `conn.execute` INSERT** (the 18-B.1 technique) so write-barriers cannot reject the
very shape the test needs.

Fixture: **CASE 1's real OII shape with ONE mutated value** -- the `2026-08-13` archive close set to
`41.41999816894531 - 0.05 = 41.36999816894531` (rendering `41.37`), **the real AMN breach
geometry**: AMN closed `30.80` against a `30.85` stop, five cents. A deep breach passes sloppy
encodings; five cents pins them.

* **Required POST-FIX result, stated in FULL** (brief S4 case 5, RD refinement 3): NOT admitted;
  decline reason `mandate_not_alive` with `clear_reason='invalidation'`,
  `clear_session=2026-08-13`; **and the row lands where AMN landed** --
  `trade_origin='manual_off_pipeline'`, `candidate_id=None`, **`hypothesis_label` NULL** (never
  as-submitted -- S2.2, and a non-NULL label would make the row permanently uncorrectable),
  **never silently a broad-watch label from the latest run**. A refusal that misfiles is not a
  refusal.
* **THE FIXTURE MUST SEED A NON-NULL SUBMITTED LABEL, and the live DB is why (harvest H4, round 2a
  22A-REV-10, sharpened by measurement).** Case 5 inherits case 1's real OII shape, and trade 25's
  real `hypothesis_label` **is NULL** (measured above). So "assert the persisted label is NULL"
  against that fixture passes an implementation that faithfully persists `req.hypothesis_label` --
  there was nothing else for it to write. **The case therefore seeds
  `req.hypothesis_label='Broad-watch baseline (watch)'` and asserts the persisted column is exactly
  SQL NULL**, which fails a persist-the-submitted-value implementation. **The WARNING log carrying
  the discarded value is asserted SEPARATELY**, so the two obligations cannot mask each other.
* **An implementation omitting the invalidation comparison ADMITS this case** and writes
  `pipeline_aplus`/12284. That is the point of the case.
#### S3.5 CASE 5 SPLITS INTO 5a AND 5b (RD, 2026-08-24)

* **CASE 5a -- breach close on a PRIOR session, fill later.** The synthetic exactly as originally
  constructed (breach at invalidation - 0.05 two sessions before the fill). Refuse
  `mandate_not_alive`, `clear_reason='invalidation'`.
* **CASE 5b -- breach close ON THE FILL SESSION**, the fill going through the pivot intraday.
  **ADMIT.** *(FLIPPED 2026-08-24 with RD's withdrawal of the carve-out; it required REFUSE for the
  few hours the carve-out existed.)* **It remains the discriminator, with the verdict inverted:**
  5a's breach is strictly earlier and every implementation refuses it, so only 5b separates
  fill-wins from any session-inclusive reading. **Docstring states BOTH that the geometry is
  synthetic -- the breach session is MOVED onto the fill session; the real AMN geometry is 5a -- and
  that the ground is SURVIVORSHIP: refusing this admits a bias, because the fastest loser is the
  fill that collapses the day it triggers, and ejecting exactly those trades censors H1's left tail
  and biases the cohort mean UP.** An implementation that refuses 5b is not being conservative; it
  is silently improving H1's apparent results.
* **CASE `5b-pre` -- THE TWIN, NOW WRITTEN (review 22A-R8-09).** 5b had been listed in the twin
  roster and its fixture never specified -- *listed is not written*, and the roster's own staleness
  is what made that invisible. **The fixture:** BYTE-IDENTICAL to 5b -- same synthetic OII geometry,
  same breach at `invalidation - 0.05` dated ON the fill session, same intraday fill through the
  pivot, same envelope, same `fill_origin` -- **with exactly ONE dimension changed: the epoch
  boundary is seeded at its REAL value instead of below the fire**, so the link mints
  `pre_barrier_reconstructed`. **Required result: NOT admitted, decline reason
  `pre_barrier_unproven`**, row lands `manual_off_pipeline` + NULL + NULL.
  * **It is a real discriminator, not a formality, and the ORDER is what makes it one.** Rung 9
    fires BEFORE the probe runs, so `5b-pre` must refuse on the TIER **without ever evaluating the
    same-session tie.** An implementation that ran the probe first would still reach
    `pre_barrier_unproven` and pass on the reason string alone -- **so the assertion also pins that
    `clear_reason` is `None` on the returned `LatchedProvenance` and that no aliveness evidence was
    recorded**, which is what distinguishes refuse-at-rung-9 from refuse-after-probing.
  * **Its docstring carries the free-dimension sentence (S3.8) naming the ONE dimension it varies**
    -- the epoch boundary -- so the pair reads as the controlled experiment it is: 5b and `5b-pre`
    differ in exactly one input and in exactly one verdict.

> ### PREMISE CORRECTION, MEASURED, AND IT CHANGES HOW 5b MUST BE BUILT
>
> The ruling reached me with the justification that *"AMN's ONLY breach close is 30.80 on
> 2026-08-07 ... breach session == fill session. AMN is the SAME-SESSION TIE."* **I re-derived it
> and the date is off by one session.** Method:
> `load_bars_with_status(cfg, 'AMN', start=2026-08-01, end=2026-08-12)`, `archive_status='ok'`,
> every bar printed:
>
> | session | close | breach vs 30.85? |
> |---|---|---|
> | 2026-08-03 | 33.00 | no |
> | 2026-08-04 | 33.25 | no |
> | 2026-08-05 | 32.80 | no |
> | **2026-08-06** | **30.80** | **YES** |
> | **2026-08-07** | **36.00** | no |
>
> Entry fill 41 is `2026-08-07 @ 36.43` (trade 20). **The breach is 08-06; the fill is 08-07; the
> breach is STRICTLY PRIOR.** The fill session's own close, 36.00, does not breach at all. This
> plan's own S0 table and S3.2 fixture already carried the correct dates (`clear_reason='invalidation'
> @ 2026-08-06`), which is how the discrepancy surfaced.
>
> **HOW IT RESOLVED, 2026-08-24.** RD verified the correction himself, then **re-opened the doctrine
> on SEMANTICS rather than on the corrected dates -- deliberately, so it could not flip on a third
> arithmetic** -- and **WITHDREW the carve-out**: his ORIGINAL bound was right all along, and the
> session-grain "correction" of it had introduced the error. **Fill-wins is uniform, invalidation
> included** (S2.3.1a), on the survivorship ground stated there. **Case 5b FLIPS from REFUSE to
> ADMIT.** It is still built as an explicitly SYNTHETIC variant -- OII's real shape, the breach
> magnitude held at invalidation - 0.05 (the real AMN MAGNITUDE, never in doubt), the breach session
> MOVED onto the fill session -- and its docstring now says both that the session relationship is
> synthetic and that the ground for admitting is survivorship, so nobody reads it as a live case OR
> as leniency.
>
> **The wider lesson, which is CHARC's and is better than the correction:** *independent
> verification means an independent DERIVATION PATH, not a second run of the same one.* Three paths
> were used here -- my archive read, the orchestrator's `data_asof` read, and RD's own -- and the
> correction held because they were genuinely independent. **The check that originally "confirmed"
> the claim had re-derived it from the same forward-looking anchor that produced it.**
>
> **INDEPENDENTLY CORROBORATED 2026-08-24, from a source that is not mine.** The orchestrator
> re-measured against `evaluation_runs.data_asof_date` -- a different anchor and a different table
> from my parquet read -- and it agrees: candidate 12189, `action_session_date = 2026-08-07`,
> **`data_asof_date = 2026-08-06`, close 30.80.** Two routes, one answer: the breach is 08-06.
>
> **AND THE ORIGINAL ERROR HAS A NAME, which is worth more than the correction.** The close had been
> anchored on `action_session_date` -- **forward-looking, the session a recommendation is FOR** --
> when a close belongs to `data_asof_date`. That is the session-anchor read/write family CLAUDE.md
> records, and **the check that "confirmed" it re-derived the claim from the SAME wrong anchor, so
> it could only ever agree.** A verification that inherits the claim's framing is not a
> verification -- exactly as a fixture that leaves a dimension free is not a discriminator (S3.8).
>
> **This is the second premise correction of this dispatch** (the first was the harvest dedup
> claim). Both were single facts everyone had reason to believe. **The one dimension nobody stated
> is the one that was wrong, which is exactly the scrutiny the gate ruling asked me to apply to my
> own synthetics -- arriving first on the ruling that asked for it.**

* **S3.5c (the corrected-date discriminator, relocated here from my withdrawn S1.9 claim):** the
  same fixture with the envelope date `2026-08-04` (after the fire, before the breach) and
  `req.entry_date='2026-08-07'` (after the breach) must be REFUSED. An implementation reading the
  session from the envelope admits it. `2026-08-04` is used because `2026-08-01` pre-dates the fire
  and would be excluded from the derivation entirely -- the error my first draft made.

### S3.6 CASE 6 -- BOUNDARY (synthetic): close EXACTLY EQUAL to the frozen invalidation -> latch survives -> **labels from the fire**

Fixture: CASE 1's shape with the `2026-08-13` close set to **exactly** `41.41999816894531`.

* **Required result: ADMITTED**, identical to CASE 1 -- `pipeline_aplus`, `12284`,
  `'A+ baseline (aplus)'` -- in the POST-BARRIER world, with its own `-pre` twin per the S3
  convention.
* **A `<=` encoding fails this case while passing CASE 5**, which is precisely why RD ruled the
  inequality and why the case is first-class rather than a companion to case 5.
* Cross-check: this agrees with the shipped
  `tests/latches/test_service_terminal.py:test_a_close_exactly_at_the_stop_does_not_invalidate`.
  If the two ever disagree, one is wrong and both tests say so.
* **The display-precision variant must vary BOTH operands (review 22A-R15-13).** My previous
  variant (close `41.4199` against the real stop) is passed by an implementation that rounds only
  the close: `round(41.4199, 2) = 41.42 < 41.41999816894531` is FALSE, so a close-only
  implementation admits it and looks correct. The discriminating fixture uses a frozen stop of
  **`41.424`** and a close of **`41.4199`**: both round to `41.42`, so only a BOTH-operands
  implementation admits. Close-only (`41.42 < 41.424` -> true -> refuses), stop-only
  (`41.4199 < 41.42` -> true -> refuses) and no-rounding (`41.4199 < 41.424` -> true -> refuses)
  are each invalidated by the required ADMIT verdict.

### S3.7 THE OMISSION LENS -- for every clause, the case that fails an implementation omitting it

| # | clause the mechanism encodes | case that fails an omitting implementation |
|---|---|---|
| 1 | broker-order-id identity | **CASE 4c** (two accepted links on one ticker) -- NOT case 4 |
| 2 | `accepted_by_broker` gate | **CASE 4d(i)** (rejected row + planted link) -- NOT case 4 |
| 2b | the linked row is the LATEST validity child | **CASE 4d(ii)** (accepted, later superseded) |
| 3 | not the windowed price heuristic | CASE 4b (NULL candidate, in-zone, no validity) |
| 3b | not "any armed latch" | CASE 4 (RHI, armed at its fill session) |
| 4 | the invalidation comparison exists at all | CASE 5 |
| 5 | strict `<`, not `<=` | CASE 6 |
| 6 | breach magnitude is five cents, not "obvious" | CASE 5 |
| 7 | display-precision rounding both sides | CASE 6 variant (`41.4199`) |
| 8 | the fill session is the CORRECTED date | CASE 5c |
| 9 | coverage: `unavailable` is not alive | case 7 -- `archive_status='unavailable'` over a non-empty window -> `aliveness_unverifiable` |
| 9b | coverage: `ok` is not COMPLETE | **case 7b (new)** -- `archive_status='ok'` with a MISSING INTERIOR NYSE session -> `aliveness_unverifiable`. Omitting per-session completeness passes case 7 and fails only this one |
| 10 | empty window is alive by construction | **case 8 (RESTORED 2026-08-24)** -- fill on the anchor session, zero bars -> ADMITTED (a naive "require bars" rule refuses this). **Between the carve-out and its withdrawal this row demanded a second input -- "exactly ONE readable, finite, non-breaching fill-session bar" -- and companions 8b/8c. All three are struck: nothing judges the fill session's close any more.** Restored rather than silently reverted |
| 11 | snapshot vs live cross-check, **stop** | case 9 -- fire's `initial_stop` mutated after minting -> `frozen_value_drift` |
| ~~11b~~ | **REMOVED -- tier-2 admission and trade 25's correction are CARVED to 22-A2 (S12).** The `--frozen-value-evidence` option, the four-criterion preflight and the replay contract go with them; the existing five-option CLI manifest pin stays GREEN |  |  |
| 12 | lapse rung forced off | case 10 -- `criteria_lapse_armed=True` with a lapse-qualifying latch -> still ADMITTED; force bypassed -> `LatchProbeInvariantError` |
| 13 | `clear_reason`, not `state` | case 11 -- a `declined` latch and a `criteria_lapsed` latch must be distinguishable; both render `state='horizon_expired'` |
| 13b | `declined` refuses | **case 11b (new)** -- resolver-level, asserting non-admission and the exact reason/session |
| 13c | `superseded` refuses | **case 11c (new)** -- resolver-level, same shape |
| 14 | all-three-or-none, with suppression | case 12 -- accepted link, keys underivable, **and the ticker IS `aplus` in the latest run** -> `manual_off_pipeline` + NULL + NULL label |
| 15 | one trade per mandate | case 13 -- a second trade citing the same fire -> `mandate_already_consumed` |
| 16 | cardinality by COUNT | case 14 -- two links sharing one broker order id -> `ambiguous_accepted_orders` |
| 17 | envelope guards | **cases 15a-15e (expanded)** -- untrusted `fill_origin`; out-of-zone price; **ticker mismatch**; **quantity mismatch**; **malformed / absent envelope**. My first draft named only the first two and claimed the set |
| 17b | per-ticker cardinality | **case 15f (new)** -- two live accepted orders on one ticker -> `ambiguous_ticker_orders` |
| 18 | `horizon` refusal | case 16 -- a fill dated past the 30-session expiry -> refused |
| 19 | the exclusion parameter | **case 17 (RE-BASED FOR OPTION C)** -- the exclusion is tested on a **POST-BARRIER synthetic**, not on trade 25: seed the epoch boundary below the fire, plant the subject trade AND its fill, and assert the correction still ADMITS at `latch_ladder`. **Omitting `exclude_trade_ids` returns `clear_reason='fill'` and refuses** -- the 22A-AR-04 defect this case exists for. *(It previously ran on trade 25 "with the tier-2 evidence supplied, admitting at `latch_ladder_tier2`". There is no tier-2 in this arc, so on trade 25 the case would now refuse `pre_barrier_unproven` at rung 9 and **never reach the exclusion parameter it is written to test** -- a case that passes for a reason unrelated to its clause.)* **Trade 25's own outcome is case 1-pre** |
| 20 | the LOCK | CASE 4 plus the S2.2(a)-(d) matrix with `cfg` PASSED |
| 21 | no-config / no-order-id declines | **case 18 (new)** -- `cfg=None` and an envelope without the key each decline with their OWN reason, not a shared one |
| 22 | decisions were READ, not merely absent | **case 19 (new)** -- inject a `load_decision_intents` failure -> `decision_evidence_unavailable`. Passes trivially against today's silent `{}` |
| 23 | decision as-of rule (`recorded_ts`) | **case 20 (new)** -- a `place` recorded AFTER the fill that outranks an earlier `decline` -> `decision_evidence_post_dates_fill`; one recorded ON the fill session -> `decision_ordering_ambiguous` |
| 24 | authorization/insert atomicity | **case 21 (new)** -- mutate the ledger between recognition and INSERT; the written row must reflect the INSIDE verdict |
| 25 | consumption is ORDER-linked | **case 22 (new)** -- an ordinary trade carrying the fire `candidate_id` but NOT this broker order must NOT block admission (a `COUNT(*)` implementation falsely refuses) |
| 26 | competitor population is live+authoritative+unconsumed | **case 23 (new)** -- a valid target beside a rejected-superseded, a consumed, and an invalidated competitor -> ADMIT, not `ambiguous_ticker_orders` |
| 27 | one archive read, one world | **case 24 (new)** -- coverage derived from `derivation.archive_closes`; a fixture whose second read would differ must not change the verdict |
| 28 | `freeze_tier` describes the CANDIDATE | **case 25 (new)** -- a pre-0037 candidate (the RHI shape) accepted AFTER the migration mints `pre_barrier_reconstructed`, never `live_at_acceptance` |
| 29 | DELETE is barriered | **case 26 (new)** -- delete-and-reinsert of the same `(id, evaluation_run_id, ticker)` must ABORT at the DELETE |
| 30 | rounding on BOTH operands | CASE 6's revised variant (stop `41.424`, close `41.4199`) |
| 31 | **the same-session tie is the LADDER's, not a stricter local rule** | **cases 28a-28c** -- horizon / declined / superseded each dated exactly ON the fill session -> **ADMIT**. A bare `clear_reason is None` implementation refuses all three. Harvest H1. (**28d, the invalidation variant, is DELETED as unconstructable -- S2.3.1b, SELF-SWEEP SS-01**) |
| 31d | **the invalidation tie branch is UNREACHABLE, and stays so** | **case 28d' (new)** -- a fixture whose only sub-stop close is dated ON the fill session yields `clear_reason is None`, because `bar_bound` is the session BEFORE. **It pins an ABSENCE**: if a future change widens the bar bound, this case fails and the tie rule's scope is revisited deliberately rather than silently gaining a fourth branch. Its docstring says so |
| 46 | the link's parent relation is coherent | **case 41a (new)** -- a raw link whose `place_intent_id` names a row that is not a `place`, or names one on a DIFFERENT candidate -> `link_parent_incoherent`. **Had no case at all** (SELF-SWEEP SS-10) |
| 47 | the fill session must BE a session | **case 41b (new)** -- `req.entry_date` on a Saturday -> `fill_session_not_a_session`. An implementation skipping the guard walks `session_offset` from a weekend and shifts the whole probe window |
| 48 | the fire must be derivable at the probe's as-of | **case 41c (new)** -- a probe whose horizon predates the fire's own action session -> `fire_not_derivable` (the S1.9 shape). **Case 27 only asserted that a WRONG implementation produces this reason; nothing asserted the CORRECT one does** |
| 49 | exactly ONE latch may contain the fire | **case 41d (new)** -- two latches whose `candidate_set`s both contain the link's fire -> `ambiguous_fire_membership`. The reason was created by the R3-06 membership fix and never given a case |
| 62 | **the link's DUPLICATED fields are BOUND to their sources** | **cases 47a-47c (new, review 22A-R7-04)** -- a raw link citing a GENUINE accepted validity row while substituting the broker order id / inflating the quantity / naming a different ticker -> `link_field_unbound`. **Rungs 1-3b check ticker, parent and outcome and would admit all three** |
| 63 | **every refusal-capable rung RECORDS its input and verdict** | **cases 48a-48k (new, review 22A-R7-05)** -- one omission test per rung; each plants an otherwise-valid admission with exactly ONE `$.authorization` entry missing and asserts REJECTION. **An implementation recording only aliveness / coverage / snapshot / tie-basis fails EIGHT of them** |
| 66 | **the ROUTE decides nothing for order-id-bearing requests** | **case 37b (new, review 22A-R7-10)** -- a link lands between the route's read and the service's transaction; the written row must reflect the INSIDE verdict. **The shipped route opens its own connection, rejects, and closes before `record_entry` opens another (`trades.py:1261`, `:1371`), so an implementation keeping that lifecycle fails this and passes every other case in the plan** |
| 67 | the minting trigger never hard-codes a tier | **case 25 + the backfill test (review 22A-R7-03)** -- a PRE-migration candidate accepted AFTER 0037 must mint `pre_barrier_reconstructed`. **An S4.2-literal implementation stamps `live_at_acceptance` and gives RHI a false structural-proof label** |
| 68 | the task ladder is RUNNABLE in its stated order | **no test -- see the CLAUSES WITH NO CASE list.** A dependency error in the ladder is caught by an executor hitting it, which is what review 22A-R7-09 prevented by catching it here |
| 69 | **the barrier is verified to EXIST at read time** | **cases 50a-50c (new, CHARC 2026-08-24)** -- both triggers present + post-barrier fire -> ADMIT; `trg_candidates_no_update` dropped -> **REFUSE `barrier_not_installed` even for a post-barrier fire**; both dropped -> same. **An implementation reading only the stored tier passes (a) and fails (b) and (c)** -- and this is the row that makes single-state coherent with CONDITION 3 |
| 51 | **the tie rule's `admission_basis` is ENFORCED, not merely declared** | **cases 39a-39c** -- a tie-basis row whose `clear_session` differs from the fill session; a tie-basis row naming `fill`; an `armed` row with a non-null `clear_reason`. Each REJECTED. Added by review 22A-R4-03, and the lens did not carry it until this sweep |
| 52 | **partial fills ADMIT; only over-quantity refuses** | **cases 15d-i / 15d-ii** -- `shares=1` against `actual_quantity=2` -> ADMIT; `shares=3` -> `quantity_exceeds_order`. **An equality implementation fails 15d-i**, which is the whole of review 22A-R5-04 |
| ~~54~~ | **REMOVED -- `uncovered_seconds` is a `cited_frozen_value_evidence_json` field and is CARVED to 22-A2 with the tier-2 evidence class (S4.3, S12).** Case 40f travels with it |  |
| 57 | **fill-wins is UNIFORM at the invalidation rung** (RD, 2026-08-24 -- the interim carve-out WITHDRAWN) | **case 5b (FLIPPED to ADMIT)** -- breach close ON the fill session, fill through the pivot intraday -> **ADMIT**. **An implementation that refuses it censors H1's left tail: the fastest loser is the fill that collapses the day it triggers, and ejecting exactly those trades biases the cohort mean UP.** 5b is the discriminator; 5a (breach strictly prior) refuses under BOTH readings and cannot separate them |
| 57b | ...and a breach on ANY EARLIER session still kills | **case 5a** -- the real AMN geometry, breach `2026-08-06` against a `2026-08-07` fill -> REFUSE. An implementation that read fill-wins as "the fill always wins" admits it |
| 58 | the invalidation date is anchored on `data_asof`, never `action_session_date` | **cases 5a / 5b fixtures**, which date every bar by its `data_asof` session and say so. **The forward-looking anchor is what produced this arc's off-by-one-session premise error (S3.5); `derive_latches` judges `DailyBar`s carrying their own session, so the mechanism is clean by construction (S2.3.5, #30) and the fixtures pin it** |
| 61 | the replaced trigger's OLD guarantee survives | **case 43 (new, CHARC CONDITION (b))** -- for every column the PRE-0037 append-only trigger protected, a barred write must STILL fail post-migration. **Computed against the OLD guarantee: a test written only against the six new columns passes a replacement that silently dropped protection on an old one** |
| 61b | DROP and CREATE are in ONE transaction | **case 44 (new, CHARC CONDITION (a))** -- the migration file carries no statement between a DROP and its CREATE, and the explicit `BEGIN`/`COMMIT` wraps both (gotcha #9: `executescript` autocommits, which would leave `provenance_corrections` momentarily unguarded) |
| 50 | a NULL frozen value refuses at the RESOLVER | **case 41e (new)** -- the junk-pivot link from S4.2 (minted with NULL frozen values, ledger write NOT blocked) carried through to admission -> `frozen_value_unavailable`. The S4.2 test proved the trigger does not RAISE; nothing proved the resolver then REFUSES |
| 31b | ...and it does NOT widen past the tie | **case 28e** -- each of the THREE dated ONE session earlier -> REFUSE. Without it, "admit on any terminal at-or-after the anchor" also passes 28a-28d |
| 31c | `fill` is EXCLUDED from the widening | **case 28f (REVISED, review 22A-R4-06)** -- another trade's `fill` terminal ON the fill session, that trade carrying a **DIFFERENT (or absent) broker order id** -> REFUSE **`mandate_not_alive`** naming `clear_reason='fill'`, the matched trade and its `fill_link_basis`. **My first version expected `mandate_already_consumed`, which does not discriminate:** if the other trade carried the SAME order id, rung 6 refuses BEFORE the probe runs, so an implementation that wrongly widened `fill` terminals passes anyway; and if it did not, `mandate_already_consumed` contradicts S2.4a's order-linked definition of consumption. Same-order consumption is tested separately at case 13 (rung 6) |
| 32 | probe selection by `candidate_set`, not identity | **case 27 (new)** -- an accepted order on a same-pivot RECONFIRMATION fire; an identity-match implementation returns `fire_not_derivable` |
| 33 | the governing place CYCLE | **case 29a (new)** -- accepted old cycle + a newer `place` with no validity -> `place_cycle_superseded` |
| 34 | cancellation history | **cases 29b-29c (new)** -- cancel before the fill -> `order_cancelled`; cancel ON the fill session -> `cancel_ordering_ambiguous` |
| 34b | ...and a cancel AFTER the fill is not consulted | **case 29d (new)** -- ADMIT. Fails an implementation refusing on any cancel at all |
| 35 | the price bound is `mandate_limit_price`, not a second rounding | **case 30a (new)** -- cap with a non-zero third decimal, fill at the `round`-up cent -> REFUSE. A `round(zone_cap,2)` implementation ADMITS |
| 35b | ...and the floored cent is still inside | **case 30b (new)** -- ADMIT |
| 35c | the validity row's `actual_limit_price` is consulted | **case 30c (new)** -- actual limit below the framework cap, fill between -> REFUSE + divergence WARNING |
| 36 | consumption evidence can be DESTROYED | **case 22b (new)** -- a prior trade whose entry fill went through split-into-partials (envelope stripped) -> `consumption_evidence_unavailable`, never a silent admit |
| 36b | ...and the replacement path now preserves it | **case 22c (new)** -- split a Schwab-envelope fill; every partial still carries `fill_origin` + `schwab_source_value_json` |
| 37 | competitor liveness is THREE-valued | **cases 23b-23d (new)** -- an unconsumed authoritative competitor with (b) `archive_status='unavailable'`, (c) a failed decision read, (d) a NULL snapshot -> `competitor_liveness_unverifiable`. An exclude-the-unresolved implementation ADMITS all three |
| 38 | `BEGIN IMMEDIATE`, not the deferred `with conn:` | **case 21 (revised)** -- a competing writer commits between the authoritative read and the INSERT; under a deferred transaction the write lands on the stale world |
| 38b | ...and it covers the NO-LINK preliminary too | **case 21b (new)** -- a request whose recognition found NO link acquires one before INSERT. An implementation reserving only on the recognised-latched path takes the ordinary path |
| 39 | rung 9 -- pre-barrier refuses by default | **every admitting case's `-pre` twin** (S3 convention). An implementation omitting rung 9 passes every base case and fails every twin |
| 40 | the epoch is itself immutable, **on EVERY write path, at SQLite's DEFAULT pragma** | **cases 35a-35c, 35n, 35p (S4.5B RULED -- no longer conditional)** -- `UPDATE`, `DELETE`, `INSERT OR REPLACE`, a plain second-row `INSERT`, and bare `REPLACE` / `INSERT OR IGNORE` each ABORT. **A TWO-trigger implementation passes 35a/35b/35n and FAILS 35c/35p**, because `REPLACE` fires DELETE triggers only when `recursive_triggers` is ON and this repo never enables it (measured -- S4.5-epoch) |
| 41 | the abort messages are LEGIBLE | **case 36 (new)** -- each barrier message contains its trigger name, `22-A`, and `reversibility header` (CONDITION 2, asserted as content not bytes) |
| 42 | required evidence keys are asserted POSITIVELY | **case 34c (new)** -- a required key omitted -> REJECTED. **PASSES against a `json_remove` closure-only implementation**, which is the whole point |
| 42b | `horizon_session` and the validity PARENT are BOUND | **cases 34d-34e (new)** -- a `horizon_session` not equal to `entry_fill_session_date`; a validity row whose `validated_place_intent_id` differs from the cited place. **`bars_through` is deliberately NOT SQL-bound** (a trigger cannot walk an exchange calendar) and is validated in the service, which is stated rather than left as an apparent omission |
| 43 | the route passes through a RECOGNISED-AND-REFUSED entry | **case 37 (new, harvest H5)** -- an invalidated linked request WITH a `pattern_evaluation_id` anchor whose latest-run origin has drifted to manual: the route must NOT reject it, or the service never writes the honest-unset row. A test covering only the ADMITTED branch passes an implementation that still rejects (c) |
| 44 | case-5's label assertion DISCRIMINATES | **case 5, revised fixture (harvest H4)** -- seeds a NON-NULL submitted label. Against trade 25's real (NULL) label the assertion passes an implementation that persists the submitted value |
| 45 | the SQL twin and the Python epoch reader agree | **case 38 (new)** -- both run over SINGLE-STATE fixtures: a candidate BELOW the boundary, one exactly AT it, one ABOVE. A single-spelling implementation cannot fail it, which is why the test runs BOTH. *(It previously ran armed-then-retired / armed-retired-armed / spurious-lower ERA fixtures; those shapes are not constructable under single-state and travel to 22-A2.)* |

### S3.8 THE FREE-DIMENSION AUDIT -- which dimensions each synthetic PINS, and which it leaves free

**Ordered at the ruling, and the ruling is its own best evidence:** neither director specified the
SESSION RELATIONSHIP of the synthetic breach. Both specified its MAGNITUDE (invalidation - 0.05)
and took that to be the discriminating dimension. **It was not** -- the session relationship was,
and it was left free, and case 5 was ambiguous between two behaviours for four rounds without
anyone noticing. **So: for every synthetic, which dimensions are PINNED, and is a FREE one doing
silent work?**

Auditing by dimension rather than case by case, because a dimension is what does the silent work:

| dimension | cases where it is LOAD-BEARING | verdict |
|---|---|---|
| **breach session vs fill session** | 5a, 5b, 6, 28a-28c | **WAS FREE, NOW PINNED.** The defect this audit was ordered for. 5a = strictly prior; 5b = ON the fill session; 6 = prior; 28a-28c = the terminal on the fill session |
| **the FILL SESSION'S OWN CLOSE** | *(none, since 2026-08-24)* | **BRIEFLY LOAD-BEARING EVERYWHERE, NOW NOT AT ALL -- and the round trip is the entry worth keeping.** Under the carve-out this dimension decided admission in every case, and I pinned it as non-breaching in every admitting fixture. **RD's withdrawal removed the clause, so the pins are struck**; nothing judges that close. **The audit's value did not depend on the answer being stable** -- it named a dimension nobody had stated, which is what let the withdrawal be executed deliberately instead of leaving pins that quietly constrained fixtures for a rule that no longer existed |
| **the BAR'S SESSION ANCHOR (`data_asof` vs `action_session_date`)** | 5a, 5b, and every bar-bearing fixture | **NEWLY PINNED 2026-08-24.** The forward-looking anchor produced this arc's off-by-one premise error, so every fixture now DATES its bars by the `data_asof` session and says so. **A dimension that was free in the DOCUMENTATION rather than in the code** -- `derive_latches` was always clean (S2.3.5) -- which is a distinct and easily-missed variety: the artifact could mislead a reader even though the mechanism could not mislead a machine |
| **competitor session relationship** | 23, 23b-23d | **WAS FREE, NOW PINNED.** A competitor's liveness is evaluated AT the fill session, so leaving its anchor/expiry free lets a fixture drift between "proven dead" and "unprovable" without the assertion changing. Each competitor's anchor, expiry and breach state are now stated |
| **the OTHER trade's fill session** | 13, 22, 22b | free, and verified HARMLESS: consumption is order-linked (S2.4a) and session-independent by construction. **Stated rather than assumed** |
| **magnitude of the breach** | 5a, 5b, 6, 6-variant | pinned throughout (0.05; exact equality; the 41.424/41.4199 pair). This is the dimension everyone DID think about |
| **rounding operands** | 6-variant | pinned on BOTH operands (review 22A-R15-13) |
| **quantity** | 15d-i, 15d-ii | pinned (1 vs 2; 3 vs 2) |
| **`freeze_tier`** | every admitting case | pinned by the `-pre` twin convention (S3), which is what that convention is FOR |
| **missing-session position** | 7, 7b | pinned INTERIOR in 7b -- a trailing gap is a different and weaker case |
| **`recorded_ts` vs the fill** | 19, 20 | pinned (before / on / after), because that IS the clause |

**The generalisation, since it is now the second time a free dimension has done silent work in this
plan** (the first was case 4c, where both windows containing the fill made an identity test pass an
identity-ignoring implementation): **a synthetic case is a claim about ALL dimensions, not only the
one it names.** The remedy that scales is not more scrutiny per case; it is stating, in each
fixture's docstring, **which dimensions the case pins and which it deliberately leaves free** -- so
a reader can see the free ones instead of reconstructing them. **Every synthetic fixture in this
plan carries that sentence.**

**CLAUSES WITH NO CASE, stated rather than left to look complete.** This list is the per-clause
discriminator lens turned on the plan's own gate: for every clause, name the case that would fail
an implementation omitting it -- **and where there is none, say so here instead of letting the
table's length imply coverage.**

* **The `pre_barrier_reconstructed` freeze tier has no case that PROVES the historical value is the
  fire's 2026-08-07 value.** By construction it cannot: the barrier cannot reach backwards and the
  snapshot did not exist then. **RD's ruling does not change this** -- it changes what the system
  DOES about it: **under Option C it REFUSES, full stop.** *(RD's ruling also created a
  verified-evidence path, and case 32f tested that VERIFICATION rather than the underlying
  historical fact; both are CARVED to 22-A2.)* **In this arc the gap is not bounded-and-recorded
  but simply REFUSED** -- a stronger posture and a larger cost. S8-L2.
* ~~**The 2.38-day uncovered window has no case at all.**~~ **CARVED to 22-A2.** The window is a
  property of trade 25's tier-2 evidence -- nothing in the repo attests `candidates.initial_stop`
  between `2026-08-07T17:30:02` and `2026-08-10T02:41:33-10:00` -- and this arc neither computes,
  records nor relies on it, because it admits no pre-barrier fire at all. **Struck rather than
  deleted, because the underlying gap is REAL and travels with the evidence class that would have
  had to bound it.** S12.
* **`candidate_criteria` immutability has no PROVING case, only a REVEALING one.** Case 31 shows
  the label moving while the pivot/stop cross-check stays clean; it asserts VISIBILITY, not a
  refusal, because with the barrier declined there is nothing to refuse on. **Labelled as a
  limitation-pinning test in its own docstring**, so its green is never read as proof the label is
  frozen. S8-L13.
* **Coverage-array truthfulness has no SQL case** (S4.3 limit 1). Cases 34a-34b deliberately assert
  that fabricated-but-coherent arrays are ACCEPTED by the trigger. The coverage FACT rests on the
  service and on case 7b. **Two of the plan's own tests therefore pin a limit rather than a
  guarantee, and both say so in their docstrings.**
* **The unauthenticated envelope's residual has no case, by definition** (S2.4.1, S8-L10): an
  envelope naming a DIFFERENT accepted order on the SAME ticker whose zone and quantity coincide,
  in a window where the cardinality rung sees one live order, is INDISTINGUISHABLE from the real
  one at every rung. A test cannot separate two things the mechanism cannot separate. **Flagged for
  CHARC/RD, V2 fix named.**
* ~~**THE TIER-2 TIME ANCHOR HAS NO PROVING CASE (L15).**~~ **CARVED to 22-A2 with the tier-2
  class** (S12), along with case 32g and the whole `origin/main`-ancestry criterion. **The hazard it
  was recorded to illustrate is KEPT, because it is about this AUDIT rather than about tier-2:** the
  entry only ever appeared because the clause did not exist when the audit was first written --
  **a discriminator audit inherits the coverage of the artifact it was run against.** The carve has
  just changed that artifact underneath it, which is why the audit is re-run here rather than
  inherited.
* **`bars_through` has no SQL case, BY CONSTRUCTION** (S4.3, review 22A-R5-02): a trigger cannot
  walk an exchange calendar, so the field is service-validated and SQL-unbound. **Row 42b names
  that as a deliberate omission rather than leaving it looking like a gap someone forgot** -- and
  it is recorded here so the next reader does not "fix" it by adding a binding that would then be
  wrong for every fill whose prior session is a holiday.
* ~~**The third epoch trigger's property is UNTESTABLE IF CHARC DECLINES IT.**~~ **WITHDRAWN
  2026-08-24: CHARC APPROVED the trigger, so the property is testable, so it is TESTED.** Under
  Option C the third trigger is a `BEFORE INSERT` barrier and its cases are **35c and 35p**
  (`INSERT OR REPLACE`; bare `REPLACE` / `INSERT OR IGNORE`), both asserted at SQLite's default
  `recursive_triggers` -- S4.5-epoch. *(His own specified case 35g, and 35f, test the ERA trigger
  and travel to 22-A2.)* **The entry is struck rather than deleted, because an honest "no case"
  that converts into a case when the blocking decision lands is the list working as intended** --
  it named the dependency instead of hiding it.
* **CONDITION 1's live pipeline run has no automated case and is not meant to have one.** It is a
  pre-merge OPERATOR gate (S9 step 0) precisely because the class it covers -- a writer on a path
  the nightly exercises that no grep saw -- is the class byte-tests cannot reach. Recording it here
  keeps the gate from being read as belt-and-braces on top of tests that already cover it. **They
  do not.**

---

## S4. SCHEMA -- migration `0037_latch_order_mandate_links.sql` (v36 -> v37)

Additive only. Explicit `BEGIN; ... COMMIT;` per gotcha #9. The version bump is the final statement
before `COMMIT` (the Phase-9 A.0 precedent). Backup gate: `pre_version == target - 1` holds for
36 -> 37.

### S4.1 The new table

`latch_order_mandate_links`: `link_id` PK; `validity_intent_id` **UNIQUE** `REFERENCES
latch_order_intents(intent_id) ON DELETE RESTRICT`; `place_intent_id` same FK; `candidate_id`
`REFERENCES candidates(id) ON DELETE RESTRICT`; `evaluation_run_id`, `ticker`, `detection_date`,
`broker_order_id` (NOT NULL, **no UNIQUE**); `frozen_pivot`, `frozen_invalidation` (both NULLABLE);
`actual_quantity`; `freeze_tier` CHECK in
`('live_at_acceptance','pre_barrier_reconstructed')` -- **TWO-valued under single-state; the
three-valued form travels with the era model to 22-A2**;
`linked_at`. **No `frozen_zone_cap`** (S2.1 property 3 -- the cap is derived at read time from the
frozen pivot, so no arithmetic is duplicated into SQL and nothing carries a false "frozen" claim).
Append-only `BEFORE UPDATE` / `BEFORE DELETE` `RAISE(ABORT)` triggers mirroring `0033:834-837`.
Value CHECKs: prices `> 0` **or NULL**; `actual_quantity > 0` or NULL; the three-predicate date
guard on `detection_date` per `0033`'s own lesson.

### S4.2 The minting trigger and the backfill

`AFTER INSERT ON latch_order_intents WHEN NEW.intent_kind='validity' AND
NEW.validity_outcome='accepted_by_broker' AND NEW.actual_broker_order_id IS NOT NULL`, inserting one
row whose **`freeze_tier` is the S4.5C `CASE` EXPRESSION, VERBATIM AND BY REFERENCE -- the minting
trigger NEVER hard-codes a tier** (review 22A-R7-03).

> **THIS LINE READ `freeze_tier='live_at_acceptance'`, UNCONDITIONALLY, in the section that
> authoritatively specifies the trigger.** Implemented literally it would have given **RHI's
> post-migration acceptance of a PRE-migration fire a false structural-proof label** -- the exact
> defect the epoch exists to prevent, written into the epoch's own migration.
>
> **It is the TWELFTH mirror site of the freeze-tier family, and the eleven-site sweep could not
> have found it: I swept for the enum's VALUE SET and this line hard-codes ONE MEMBER of it.**
> **A value-set sweep does not find a hard-coded single member** -- that generalises past this arc
> and past this enum. **Re-swept on the corrected basis** (`grep "'live_at_acceptance'"` and each
> sibling member separately, rather than the tuple): the only other single-member site was the
> backfill below, now also derived. **Thirteen sites, and I am not asserting thirteen is the set
> either** -- the standing defence is the SQL-vs-Python drift test, which is the one instrument that
> does not depend on my choosing the right grep.

**IT MUST BE INCAPABLE OF RAISING, and my first draft only asserted that it would not
(review 22A-AR-09).** `candidates.pivot` / `initial_stop` are unconstrained REAL columns
(`0001_phase1_initial.sql:24-41`) and `_validate_fire` (`swing/latches/service.py:162-180`) proves
unusable values are representable; the link table's own `> 0` CHECKs would then abort the LEDGER
write on a junk fire. **So each copied value is guarded at the source:**

```
CASE WHEN typeof(c.initial_stop) = 'real' AND c.initial_stop > 0
     THEN c.initial_stop ELSE NULL END
```

and likewise for the pivot. A NULL lands, admission later refuses `frozen_value_unavailable`, and
the operator's execution record is never blocked by cohort bookkeeping (`0036:26-38`). **Test: a
raw-INSERT acceptance on an A+ candidate carrying a negative pivot must succeed on the ledger and
produce a link row with NULL frozen values.**

Backfill in the same migration as a general `INSERT ... SELECT` over the ledger (not a hand-written
OII row), **deriving `freeze_tier` through the SAME `CASE` expression rather than stating a
constant** -- the second single-member site the corrected sweep found. Its EXPECTED result today is
exactly one row at `pre_barrier_reconstructed`, and the test asserts that as an OUTCOME of the
derivation, not as an input to it. Verified against the live table: intent 2 is the only accepted
validity row.

### S4.3 SIX `ADD COLUMN`s on `provenance_corrections`, and two trigger replacements

```
admission_tier                     TEXT NOT NULL DEFAULT 'last_word'
cited_latch_link_id                INTEGER REFERENCES latch_order_mandate_links(link_id) ON DELETE RESTRICT
cited_latch_validity_intent_id     INTEGER REFERENCES latch_order_intents(intent_id)     ON DELETE RESTRICT
cited_latch_place_intent_id        INTEGER REFERENCES latch_order_intents(intent_id)     ON DELETE RESTRICT
cited_latch_broker_order_id        TEXT
cited_latch_probe_json             TEXT
```

> **CARVED TO 22-A2 FROM HERE (Option C) -- THE SEVENTH COLUMN AND EVERYTHING THAT VALIDATED IT.**
> This block previously specified `cited_frozen_value_evidence_json` in full: its required-key
> schema (`evidence_version`, `artifact_path`, `artifact_commit_sha`, `quoted_text`,
> `ruling_citation`, `anchor_strength`, `descendant_count`, `evaluated_at`, `verification_method`,
> `resolved_remote_ref_sha`, `time_anchor_residual`, the `quoted_*` bindings, `fire_run_epoch`,
> `record_epoch`, `uncovered_seconds`, `uncovered_window_prose`), the SQL enforcement of
> `uncovered_seconds = record_epoch - fire_run_epoch`, and **cases 40a-40f**. **All of it belongs
> to RD's tier-2 evidence class and travels to 22-A2 with it (S12), AS RULED.**
>
> **It is struck rather than left standing, because S4.3 is the section an executor builds the
> migration from** -- a fully-specified column beside a one-line note that the column is carved is
> a build instruction, not a footnote, and the survivors-by-inertia class is at its most expensive
> exactly here. **The reduced arc's tier enum is two-valued, so nothing in 22-A can even reference
> the column.**

**SIX `ADD COLUMN`s** -- the seventh, `cited_frozen_value_evidence_json`, was RD's tier-2 citation
(S1.5.3a) and is CARVED to 22-A2 with the class it served (S12). The tier enum
is `('last_word','latch_ladder')` -- **two-valued in this arc**; `latch_ladder_tier2` arrives with
22-A2.

`admission_tier` takes a constant default, so `NOT NULL DEFAULT` is legal and the existing CADL row
becomes `'last_word'` -- which is true of it. FK columns default NULL, as SQLite requires.

**Why triggers, not table-level CHECKs.** `ALTER TABLE ADD COLUMN` cannot add a table-level CHECK,
and the paired-NULL rule (*`last_word` -> all five citation columns NULL; `latch_ladder` -> all five
NON-NULL*) is cross-column. The only alternative is rebuilding the audit table of record --
the D30 class, on a table with append-only triggers, for a rule a trigger states exactly.
**Implementation note:** verify at the sqlite prompt whether a *column-level* CHECK is accepted in
`ADD COLUMN` on the installed version before writing either form; `0036` records four separate
CHECK-semantics surprises and this repo verifies rather than assumes.

* `trg_provenance_corrections_citation_graph` -- DROP + CREATE with the existing eight relations
  verbatim plus: the tier/paired-NULL rule; the link row exists, its `candidate_id` equals
  `cited_candidate_id`, its `broker_order_id` equals `cited_latch_broker_order_id`, and its
  `validity_intent_id` / `place_intent_id` equal the two cited intents; the validity intent is
  `accepted_by_broker`; **and `cited_latch_probe_json` carries a VERSIONED, EXACT evidence schema,
  every field cross-checked against the row's own columns.** My first draft checked five fields and
  review 22A-AR-13 showed that a raw insert could still claim `latch_ladder` while omitting the
  evidence admission actually rests on. Required and cross-checked: `$.evidence_version`;
  `$.fire_candidate_id = cited_candidate_id`; `$.ticker` = the trade's; `$.fill_session =
  entry_fill_session_date`; `$.clear_reason` JSON-null; `$.criteria_lapse_forced_off = 1`;
  `$.freeze_tier` = the link's; **`$.frozen_invalidation_raw` and `$.live_invalidation_raw`, each
  BOUND by trigger subquery to its source** -- the frozen value to the cited link's column, the
  live value to the cited candidate's -- because a number the row supplies about itself proves
  only that the row is self-consistent (review 22A-R15-09). **Each binding is a plain `=` against
  the source REAL and is NEVER wrapped in `round()`, and the two raw values are NEVER compared to
  EACH OTHER in SQL**; the service's verdict travels instead as `$.invalidation_equal_at_dp`
  (integer `1`), with `$.compare_dp` = `2`. **The same three for the pivot.** This clause used to
  read *"present and EQUAL and each bound to its source"* and that form REJECTED truthful rows two
  different ways -- **review 22A-R8-10, and THE SINGLE ROUNDING AUTHORITY below is the ruled fix**; **and every object closed exactly, via `json_remove(<obj>, <every allowed
  key>) = '{}'` at each level**, so an evidence blob cannot carry extra keys or omit required
  ones; `$.coverage` either `{"window_empty": true}` or
  `{"expected_sessions": [...], "observed_sessions": [...], "missing_sessions": []}` with
  `json_array_length($.coverage.missing_sessions) = 0` and the expected/observed arrays
  compared **ELEMENT BY ELEMENT via `json_each`, not by length** (review 22A-R15-09: equal lengths
  plus an empty `missing_sessions` accepts two unrelated or duplicated arrays), with duplicate
  rejection and an ISO-date type check on every element;
  **`$.horizon_session` and `$.bars_through`, which my previous draft collapsed into one
  `$.probe_session` with two incompatible definitions (review 22A-R5-02).** S3.1 requires
  `probe_session='2026-08-14'` for trade 25's `2026-08-17` fill -- the DERIVATION's own prior
  exchange session (`swing/latches/reader.py:890-893` derives it; `:948-950` loads bars only
  through it) -- while S4.3 required the trigger to enforce `$.probe_session =
  entry_fill_session_date`, i.e. `2026-08-14 = 2026-08-17`. **A truthful trade-25 correction could
  not have been written: it would ABORT, or record the fill session as the probe session and lie.**
  Split: **`$.horizon_session` IS the fill session and IS bound in SQL** to
  `entry_fill_session_date`; **`$.bars_through` is the exchange-calendar-derived prior session and
  is validated in the SERVICE, not in SQL** -- a trigger cannot walk an exchange calendar, and
  pretending otherwise is how the collision happened. S3.1's `2026-08-14` is `bars_through`.
  **`$.admission_basis`, and `$.clear_reason` / `$.clear_session` per the S2.3.1a matrix rather
  than unconditionally JSON-null (review 22A-R5-03).** My previous draft stated the two-branch
  matrix in S2.3.1a and left this closed object requiring `$.clear_reason` to be JSON null with no
  `admission_basis` key at all -- **so the closure check itself would have REJECTED the very rows
  the tie rule admits, and a residual of a fix landed in the same round that made it.** The
  allowed-key closure now includes both fields, and the SQL enforces: `admission_basis` in
  `('armed','subject_fill_wins_same_session_tie')`; under `armed`, `clear_reason` and
  `clear_session` are JSON null; under the tie basis, `clear_reason` is one of the **THREE
  REACHABLE** reasons -- `declined`, `superseded`, `horizon`, **never `invalidation` and never
  `fill`** (S2.3.1b: an invalidation cannot carry the fill session's date, so a row claiming one is
  incoherent by construction) -- and `clear_session` **equals `entry_fill_session_date`** by
  binding.
  > **THE FILL-SESSION-CLOSE EVIDENCE FIELDS ARE WITHDRAWN 2026-08-24, AND THE STANDING RULE THEY
  > PRODUCED IS KEPT.** Review 22A-R6-01 was right that S2.3.1c's comparison was evaluated and never
  > recorded, and I added four bound fields for it. **RD's withdrawal of the carve-out removed the
  > comparison, so the fields are load-bearing for nothing and are struck** -- keeping them would
  > persist evidence about a check that no longer exists, which is its own species of false
  > provenance. **What SURVIVES on its own merits, because it was never about that instance:**
  >
  > **If a clause can REFUSE an admission, the evidence blob must record the INPUT it judged and
  > the VERDICT it reached.** An admission whose evidence cannot distinguish *"the check passed"*
  > from *"the check never ran"* is indistinguishable from an unchecked admission at audit time.
  > **That rule stands and governs every clause below and every clause added later.**

  **AND THE RULE WAS ASSERTED WITHOUT BEING ENFORCED, WHICH IS WORSE THAN NOT ASSERTING IT (review
  22A-R7-05).** I generalised it from one instance and never applied it to the rungs that already
  existed: the blob recorded aliveness, coverage, snapshot values and the tie basis, and **NOTHING
  for eight refusal-capable rungs** -- latest-validity authority, governing place, cancellation,
  consumption-scan integrity, competitor population, epoch continuity, the envelope guards
  (origin / ticker / quantity / price), and decision-time ordering. **At audit, "these checks
  passed" was indistinguishable from "these checks never ran" across most of the ladder** -- the
  exact defect the rule forbids, inside the section that states it. **A rule endorsed and not
  enforced reads as coverage, which is the same failure as an unconstructable case counted as
  coverage.**

  **`$.authorization` -- a CLOSED, VERSIONED object with one entry PER REFUSAL-CAPABLE CLAUSE.**
  Each entry carries `{input, verdict}`; `verdict` is `'pass'` for an admission (a non-pass in any
  entry contradicts the admission and the trigger REJECTS the row). Closure by
  `json_remove(<obj>, <every key>) = '{}'` plus a `json_type` presence assertion per entry, so a
  MISSING entry is rejected rather than read as a pass.

  **THE KEY SET IS DERIVED, NOT HAND-LISTED (review 22A-R8-09's class, applied before it bites a
  fourth time).** The entries are exactly the **refusal-capable members of the S5.1 decline-reason
  roster** -- the eleven ladder rungs of S2.4 plus the FIVE envelope guards, enumerated separately
  rather than lumped. A test derives the expected key set from that roster and asserts the
  migration's closure list matches it, **so the two cannot drift**; a hand-maintained key list is
  the same instrument as the count it replaced.

  **THE ENVELOPE GUARDS ARE FIVE ENTRIES, NOT ONE (review 22A-R8-05).** `fill_origin`, ticker,
  quantity, the framework price bound and the broker-limit bound each refuse independently, so one
  lumped `envelope_guards` entry cannot distinguish *"all five passed"* from *"one ran and four
  never did"* -- which is the exact defect the standing rule forbids, committed inside the closure
  written to enforce it.

  **SQL-BOUND vs SERVICE-VALIDATED, and this line now carries an OBLIGATION rather than only a
  disclosure.** **SQL-BOUND** means the recorded `input` is **bound by subquery to its source**
  (the link, the two intents, the candidate, the fill, the epoch row, the link's stored
  `freeze_tier`), so a fabricated input is rejected rather than merely present.
  **SERVICE-VALIDATED** means SQL asserts PRESENCE, TYPE and `verdict='pass'` and nothing more,
  **and the plan says so rather than implying SQL validates all of it.**

  **THE MEMBERSHIP IS NOT LISTED HERE.** It was, and the list rotted: this paragraph said *"rungs
  7 and 8 and the five envelope guards"* while `22A-R9-06` had already moved all five guards to
  SQL_BOUND and the migration binds them. The single roster is **L17's closure-checked region**
  (S8), derived from `AUTHORIZATION_CLAUSES` + `PROBE_GUARD_CLAUSES` and held against migration
  0037 in both directions by `tests/data/test_22a_al3_closure.py`. *Measured at that check: 14
  SQL-bound and 5 service-validated of 19 clauses.*

  > **WHY THIS PARAGRAPH EXISTS: THE CLOSURE I AUTHORED TO ENFORCE THE AUDIT RULE DID NOT ITSELF
  > CLOSE (review 22A-R8-05 -- the R7-05 class recurring ON R7-05's own fix, one day later).**
  > Cases 48a-48k tested **PRESENCE ONLY**. They never mutated an entry's `input` while keeping
  > `verdict='pass'`, so **a trigger requiring eleven keys and eleven passes accepted fabricated
  > inputs for every one of them** -- an admission whose evidence says "these checks passed" while
  > the recorded inputs are invented is indistinguishable at audit from an unchecked admission,
  > which is the rule verbatim. **Presence is not fidelity, exactly as existence is not
  > completeness.**

  **THE CASES, in three groups so the verdict matrix is explicit:**

  * **48a-48p -- OMISSION, one per entry (REJECT).** Sixteen, not eleven: the eleven rungs plus the
    five envelope guards now that they are separate. Each plants an otherwise-valid admission with
    exactly ONE entry missing. **An implementation recording only aliveness / coverage / snapshot /
    tie-basis fails thirteen of them.**
  * **49a-49i -- INPUT FIDELITY on the SQL-BOUND rungs (REJECT).** Nine, one per bound rung. Each
    plants a complete `$.authorization` with every `verdict='pass'` and **exactly one entry's
    `input` mutated away from its source** -- a substituted broker order id in rung 1's input, a
    different place intent in rung 2's, a `rejected_by_broker` outcome in rung 3's, and so on.
    **Each must be REJECTED by the binding subquery. Every one of them PASSES against the
    presence-only implementation, which is the whole of review 22A-R8-05.**
  * **49j -- the SERVICE-VALIDATED LIMIT, pinned honestly (ACCEPT).** A fabricated `input` on a
    SERVICE-VALIDATED clause is **ACCEPTED** by the trigger, and the case's docstring says so:
    SQL cannot reach a scan result or fold state, so this is a LIMIT of the trigger and not a
    guarantee -- the same shape as 34a/34b/34f. **Declared at S8-L17 with its reason**, because
    a limit stated in a docstring and nowhere else is how a limit becomes a surprise. *The case
    DERIVES its scope from `AUTHORIZATION_CLAUSES` rather than naming members; this bullet used
    to say "rung 7, 8 or an envelope guard", which `22A-R9-06` had already falsified -- the
    EIGHTH hand-copy of this roster, and the one no token grep for the others could find.*

  `$.archive_status = 'ok'` unless the window is empty. Same
  `CASE WHEN json_valid(...) THEN COALESCE(..., 0) ELSE 0 END` idiom, for the same
  NULL-passes-a-CHECK reason recorded at `0036:530-560`. **Existence is not completeness -- the trap
  `0036` was itself rewritten for, arriving here one layer up.**

  **WHAT THIS TRIGGER CLAIMS, NARROWED TO WHAT IT CAN ESTABLISH (review 22A-R3-10).** My previous
  draft called it an "EXACT evidence schema" that validates the coverage proof. **It does not, and
  cannot.** Three limits, now stated in the migration's own comment block rather than only here:

  1. **Element-wise equality of `expected_sessions` and `observed_sessions` proves the two arrays
     agree with EACH OTHER, not with the NYSE calendar or with the archive.** Two identical
     fabricated arrays pass -- including two EMPTY arrays for a non-empty window. A trigger cannot
     enumerate a session calendar. **The trigger's claim is therefore STRUCTURAL validation of a
     row's internal coherence, plus the cross-bindings below; the coverage FACT is established by
     the service at admission and by case 7b, not by SQL.**
  2. **`json_remove(<obj>, <every allowed key>) = '{}'` rejects EXTRA keys but does not establish
     that every REQUIRED key exists**, because SQLite renders both a missing path and a JSON null
     as SQL NULL -- the exact trap `0036` documents. **Fix: every required field additionally
     carries a `json_type(<obj>, '<path>') IS NOT NULL` check with its expected type
     (`'integer'` / `'text'` / `'array'` / `'null'`),** so presence is asserted positively rather
     than inferred from the closure check.
  3. **`$.probe_session` was named and never BOUND.** It must equal the row's
     `entry_fill_session_date`, by trigger subquery, for the same reason the frozen/live values are
     bound: a number the row supplies about itself proves only self-consistency.

  **Plus the parent relation R3-10 found missing:** the cited validity intent's
  `validated_place_intent_id` must equal `cited_latch_place_intent_id`, by subquery. Without it a
  raw link can assert a false parent while every other check passes.

  **Raw-INSERT counterexamples, each its own case: 34a** two identical fabricated non-empty arrays
  (must be ACCEPTED, and the case's docstring says so explicitly -- it is the limit being pinned);
  **34b** two empty arrays with `window_empty` absent (ACCEPTED, same limit, same labelling);
  **34c** a required key omitted (REJECTED by the `json_type` check, and it PASSES against a
  closure-only implementation -- this is the discriminating one); **34d** a mismatched
  `probe_session` (REJECTED); **34e** a mismatched validity parent (REJECTED).
* `trg_provenance_corrections_append_only_update` -- DROP + CREATE with **all SIX** new columns
  in the byte-identical list, **each compared with `IS`, never `=` (review 22A-R15-10)**. **SIX of
  the six are NULLABLE** (only `admission_tier` carries `NOT NULL DEFAULT`), and `NULL = NULL`
  evaluates to NULL, which makes the `WHEN` guard NULL and **does not fire the trigger** -- so an `=` comparison would silently permit a rewrite of exactly the
  columns that carry the latch citation. The shipped trigger already uses `IS` for its nullable
  columns for this reason (`0036:646-686`). **The test must perform REAL updates --
  NULL->value, value->NULL, and value->different-value for every one of the SIX -- and assert each
  aborts; asserting that a column NAME appears in the trigger text passes against `=` and proves
  nothing.** **Not optional:** the shipped trigger enumerates every column, so a column
  added without updating it becomes freely rewritable on an append-only audit table. The test walks
  `PRAGMA table_info` rather than re-typing the roster -- the closure check the recipe prescribes,
  because a hand-maintained list fails the same way as the count it replaced.

#### S4.3a THE SINGLE ROUNDING AUTHORITY (RD's ruled principle -- review 22A-R8-10, MEASURED BY EXECUTION)

**RD's principle, applied verbatim: a comparison is performed ENTIRELY IN ONE DOMAIN. A
Python-rounded value must never meet a SQLite-rounded value across an equality.** His name for what
it prevents is exact -- *a false refusal wearing a precision costume.*

**THE DEFECT, IN THE CLAUSE ABOVE AS IT PREVIOUSLY READ.** The service admits when
`round(frozen, PRICE_DP) == round(live, PRICE_DP)` (S2.3.2; `swing/latches/service.py:795` is the
same idiom for the breach comparison, and `PRICE_DP = 2` is single-sourced at
`swing/latches/constants.py:91`). The citation trigger required `$.frozen_invalidation` and
`$.live_invalidation` to be *present and EQUAL* while each was *bound by subquery to its raw source
column*. **That is TWO independent defects in one clause, either of which REJECTS a truthful,
service-generated evidence row:**

1. **THE PRECISION-GRAIN SPLIT.** Bound raw AND required equal to each other, the trigger demands
   **RAW** equality -- strictly stronger than the `PRICE_DP` equality the service actually judged.
   Every sub-cent divergence the service correctly tolerates ABORTS the correction. **This half is
   independent of rounding entirely and is the larger of the two**, because 94% of live
   `candidates.pivot` values carry more than two decimals (12,074 of 12,824 -- measured).
2. **THE ROUNDING-DOMAIN SPLIT.** Repairing (1) by writing `round(...,2)` into the trigger is
   WORSE, because **Python and SQLite do not round the same way.** Python's `round` is
   half-to-EVEN on the exact binary double; SQLite's `round()` is half-AWAY-from-zero.

**MEASURED, NOT ASSERTED -- executed in this session against `sqlite3` and against the live DB:**

| value | Python `round(v,2)` | SQLite `round(v,2)` | agree? |
|---|---|---|---|
| `1.125` | `1.12` | `1.13` | **NO** |
| `0.625` | `0.62` | `0.63` | **NO** |
| `2.675` | `2.67` | `2.67` | yes |
| `41.4199` | `41.42` | `41.42` | yes |

**The divergent family is EXACTLY the values whose fractional part is `.125` or `.625`** -- the
exact binary midpoints at a 2-dp boundary, i.e. the eighth-dollar prices. Method: a scan of all
**10,000** three-decimal half-cent values in `0.005..99.995` returns **200 divergent (2.0%)**, and
every one is an exact dyadic rational. *(`.375` and `.875` are also exact binary but round the same
way in both domains, which is why "half-cent values" over-states the family and "eighths" does
not.)*

**AND IT IS LIVE, NOT THEORETICAL.** The same comparison run over the production database finds
**12 of 12,824 `candidates.pivot` rows and 12 of 12,824 `candidates.initial_stop` rows** sitting on
the divergent family: pivots WULF `22.625` (x3), ATOM `11.125`, DHC `9.625`, DOC `22.125` (x2),
ROIV `36.625`, BBY `84.125`, ARKG `43.125` and `44.625`, SVIX `27.125`; stops WRBY `22.125` (x10),
HYLN `2.625`, RSI `28.625`. **Each is a fire whose truthful correction row would be ABORTED by its
own citation trigger.** Method: `SELECT` every non-NULL value, compare Python `round(v,2)` against
`SELECT round(?,2)` executed in SQLite, count the disagreements.

> **THE RULE, GOVERNING EVERY PRICE MIGRATION `0037` TOUCHES:**
>
> **THE SERVICE IS THE ONLY ROUNDING AUTHORITY. SQL STORES AND BINDS; IT NEVER ROUNDS, AND IT NEVER
> COMPARES TWO INDEPENDENTLY-SOURCED PRICES TO EACH OTHER.**

Encoded as three obligations, each testable:

* **The blob carries the RAW operands** -- `$.frozen_invalidation_raw`, `$.live_invalidation_raw`
  and the pivot pair -- each bound by subquery to its source column with a plain `=` on the REAL.
  That is an **IDENTITY** check, same value and same domain, so no rounding arises and no
  cross-domain comparison exists to diverge.
* **The blob carries the SERVICE'S VERDICT as a datum, not as something SQL recomputes:**
  `$.invalidation_equal_at_dp` and `$.pivot_equal_at_dp`, each integer `1`, and `$.compare_dp`,
  integer `2`. The trigger asserts the verdicts are `1` and that `$.compare_dp = 2` -- **binding
  the precision the service used, so a later `PRICE_DP` change cannot silently re-interpret an old
  row.** All three join the closed-key set and each carries its `json_type` presence assertion.
* **A GREP GATE ON THE MIGRATION ITSELF:** a test asserts `0037` contains **no `round(`** in any
  price-bearing position. Without it the rule is a paragraph, and the single most likely way to
  lose it is a later reader "repairing" the identity check into a rounded one -- which is precisely
  how this defect arrived.

**THE RESIDUAL, DECLARED WITH ITS REASON (S8-L16).** SQL can no longer verify that
`_equal_at_dp` is the CORRECT rounding of the two raw operands; that binding belongs to the
service, which is the party that admits. A raw INSERT could cite two genuinely-correct raw values
and fabricate a `1` verdict over them. **This is strictly SMALLER than what the previous clause
exposed** -- both raws stay bound to the cited link and the cited candidate, so a forger still
cannot name a different mandate; he can only assert that two correctly-cited values compared equal
when they did not. **It is the unavoidable price of the rule: ANY SQL-side recomputation
re-creates the cross-domain comparison the rule exists to forbid.** Stated as a limitation rather
than papered over, in the same spirit as S4.3's limits 1-3.

**Cases 34f and 34g, and 34g is the discriminator for the RULE rather than for a field:**

* **34f** -- correct raw operands beside a FALSE `$.invalidation_equal_at_dp = 1`: **ACCEPTED**,
  with a docstring saying it pins the LIMIT and not a guarantee, the same honest shape as 34a/34b.
* **34g** -- a correction on a fire whose frozen and live stop are BOTH `22.125` (**the live WRBY
  geometry**, candidate ids in S4.3a's measurement above): **ACCEPTED.** *An implementation that
  writes `round(json_extract(...),2) = round(c.initial_stop,2)` into the trigger REJECTS it, and
  that implementation passes every other case in this plan.* **This is the case that would have
  caught the defect, and no case in the plan could have.**

### S4.4 Python mirrors, in the SAME task (#11)

`swing/data/models.py` gains `LatchOrderMandateLink` and **SIX** fields on
`ProvenanceCorrection` -- **one non-NULL `admission_tier` plus FIVE nullable citation fields** --
with `__post_init__` mirroring the two-valued tier enum, the paired-NULL rule and the two-valued
freeze-tier enum;

> **THIS COUNT HAS NOW MOVED TWICE, AND LEFT PARAPHRASES BEHIND BOTH TIMES.** SIX -> SEVEN when
> RD's ruling landed (review 22A-R4-07: three sites did not move -- the append-only paragraph still
> said "six" and "five of the six", and this paragraph still said six). **SEVEN -> SIX when Option C
> carved the tier-2 citation column, and SEVEN sites did not move with it** -- S0.1's declared
> envelope, lens row 61, this paragraph, the append-only trigger's three phrasings, and CHARC's
> CONDITION (b) restatement. **A count is a claim, and a claim propagates by PARAPHRASE**, which is
> why the sweep greps the WORDS `six`, `five`, `seven` and `all three` rather than the column names
> -- and why the append-only test walks `PRAGMA table_info` instead of a re-typed roster.
`swing/data/repos/latch_order_mandate_links.py` (read + the COUNT-based lookup) and the widened
`provenance_corrections` repo derive their column lists rather than re-spelling them;
`PROVENANCE_ADMISSION_TIERS` and `LATCH_FREEZE_TIERS` are single frozensets consumed by model,
service and CLI. A drift test asserts the SQL enums and the Python frozensets hold the same values.

### S4.5 The `candidates` IMMUTABILITY barrier -- UPDATE **and DELETE** -- MANDATORY (Task 2)

```
CREATE TRIGGER trg_candidates_no_update BEFORE UPDATE ON candidates
BEGIN SELECT RAISE(ABORT, 'candidates rows are immutable: a re-evaluation appends a new row'); END;
CREATE TRIGGER trg_candidates_no_delete BEFORE DELETE ON candidates
BEGIN SELECT RAISE(ABORT, 'candidates rows are permanent: the latch identity space depends on it'); END;
```

**This is the arc's PROOF of RD's gate for every fire created after the barrier (S1.5.3).**

#### S4.5-replace THE BARRIER IS FAIL-OPEN TO `REPLACE` TOO -- AND THIS IS THE LOAD-BEARING TABLE

**CHARC amended the CLAUDE.md `REPLACE` gotcha off the epoch finding (S4.5-epoch) on the ground that
it GENERALISES: any DELETE-trigger barrier in this codebase is fail-open to `REPLACE`. He directed
this plan to check the `candidates` barrier itself. IT HAS THE SAME HOLE, and it is worse here.**

**MEASURED, at production settings** (`recursive_triggers` left at its default OFF;
`foreign_keys=ON` exactly as `swing/data/db.py:119` sets it), against the real `candidates` shape --
which carries **TWO conflict targets**: `id INTEGER PRIMARY KEY` and `UNIQUE(evaluation_run_id,
ticker)` (`0001_phase1_initial.sql:24-41`):

| statement | with UPDATE+DELETE triggers only | outcome |
|---|---|---|
| `UPDATE` | aborts | guarded |
| `DELETE` | aborts | guarded |
| `INSERT OR REPLACE` conflicting on `UNIQUE(evaluation_run_id, ticker)` | **SUCCEEDS** | **id moved `12284` -> `12285`; pivot/stop rewritten; `candidate_criteria` CASCADE-WIPED 1 -> 0** |
| bare `REPLACE` conflicting on the rowid PK | **SUCCEEDS** | id preserved, **pivot/stop rewritten, `candidate_criteria` CASCADE-WIPED** |

**The UNIQUE path is precisely the catastrophe S4.5A names as the DELETE half's whole reason:**
*"`candidates.id` is a reusable rowid, and a deleted-and-reused id would silently repoint every
citation at a different row (the `fills.fill_id`-reuse class)."* **A `REPLACE` reaches it while both
barrier triggers sit present, canonical and unfired** -- so **S2.4d.1's integrity check cannot see
this**, body comparison and all. The triggers are not altered; they are BYPASSED.

**ONE THING INCIDENTALLY PROTECTS THE WRONG HALF, and it must not be mistaken for a defence.**
Re-run with a citing link row present (`candidate_id REFERENCES candidates(id) ON DELETE RESTRICT`,
S4.1), BOTH `REPLACE` paths are **BLOCKED by the foreign key**. **So the FK covers the
POST-acceptance population and leaves the PRE-acceptance population fully exposed** -- and
pre-acceptance is exactly the window that matters, because **the link copies `frozen_pivot` /
`frozen_invalidation` from `candidates` AT MINT TIME.** A `REPLACE` before acceptance rewrites the
very values that are then frozen and stamped `live_at_acceptance`. **The arc's structural proof
would be true of a row whose numbers had been silently replaced.**

**THE FIX -- and it CANNOT be the epoch's, because `candidates` must accept ordinary INSERTs every
night.** A blanket `BEFORE INSERT` barrier is unavailable. What is available is a **CONFLICT-scoped**
one: refuse an INSERT that would collide with an existing row, so `REPLACE` can never reach its
delete half.

```sql
CREATE TRIGGER trg_candidates_no_replace BEFORE INSERT ON candidates
WHEN EXISTS (SELECT 1 FROM candidates
              WHERE (evaluation_run_id = NEW.evaluation_run_id AND ticker = NEW.ticker)
                 OR (NEW.id IS NOT NULL AND id = NEW.id))
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_candidates_no_replace: candidates rows are PERMANENT
  from migration 0037. A conflicting INSERT (INSERT OR REPLACE / REPLACE) would DELETE the existing
  row, bypassing trg_candidates_no_delete, reusing its id and cascade-wiping candidate_criteria. A
  re-evaluation APPENDS a new row under a new evaluation_run_id. To retire the barrier see the
  reversibility header of 0037_latch_order_mandate_links.sql.'); END;
```

**VERIFIED BY EXECUTION that it closes the hole WITHOUT touching the nightly** (default pragma):

| statement | required | measured |
|---|---|---|
| ordinary INSERT, **new run**, same ticker | **SUCCEED** | SUCCEEDS |
| ordinary INSERT, **new ticker**, same run | **SUCCEED** | SUCCEEDS |
| `INSERT OR REPLACE` on the UNIQUE | ABORT | aborts |
| bare `REPLACE` on the rowid PK | ABORT | aborts |
| `INSERT OR IGNORE` on a duplicate | ABORT | aborts |

**`BEFORE INSERT` triggers fire BEFORE conflict resolution deletes anything** -- that is the
property the fix rests on, and it is measured rather than assumed.

**TWO BEHAVIOUR CHANGES, DECLARED (S8-L18) rather than discovered at the CONDITION-1 pipeline run:**
**(a)** `INSERT OR IGNORE` on a duplicate candidate now ABORTS where it previously no-op'd, and
**(b)** a plain duplicate INSERT now aborts with the BARRIER message rather than SQLite's `UNIQUE`
message -- same outcome, different text, and the barrier's text is the more useful of the two
(CONDITION 2). **Neither is reachable from production today** (below), but CONDITION 1's live
pipeline run is the instrument that proves it, and **S9 step 0 is where it gets proven.**

**PRODUCTION REACHABILITY, with the search that established it and the incidence.**
`grep -rniE 'insert +or +replace|replace +into' swing/ --include=*.py --include=*.sql` returns
**ZERO executable statements** -- every hit is a comment or docstring FORBIDDING the idiom (the
repo carries a long-standing convention against it: `chart_renders.py:4`, `latch_view_events.py:6`,
`schwab_api_calls.py:12`, `reconciliation_corrections.py:9`, and eleven more).
`grep -rniE 'insert +or +ignore' swing/` returns **three hits, all in migrations `0008` and `0026`,
all against `hypothesis_registry`, none against `candidates`**. `insert_candidates`
(`swing/data/repos/candidates.py:41-53`) uses a **plain `INSERT`**. **So the hole is
SERVICE-prevented, not schema-prevented, at an incidence of ZERO today.**

**And that is exactly why it is fixed rather than declared.** This plan's own S3.8 refuses
writer-absence as evidence (D36), and **the barrier IS the arc's proof** -- a structural guarantee
resting on "no writer currently spells it that way" is the posture the barrier exists to replace.
**Cases 51a-51e** are the five rows of the verification table above, **each asserting the DEFAULT
pragma rather than setting it.** *(A two-trigger implementation passes the two ordinary-INSERT
rows and FAILS the three conflict rows.)*

#### S4.5-epoch THE SINGLE-STATE EPOCH TABLE, AND WHY IT TAKES THREE TRIGGERS RATHER THAN TWO

```sql
CREATE TABLE candidates_immutability_epoch (
  epoch_id                    INTEGER PRIMARY KEY CHECK (epoch_id = 1),
  max_candidate_id_at_barrier INTEGER NOT NULL,
  applied_at                  TEXT    NOT NULL);
INSERT INTO candidates_immutability_epoch VALUES (1, <MAX(candidates.id) at migration time>, ...);
-- the three triggers are created AFTER the seeding INSERT, in the same transaction:
CREATE TRIGGER trg_candidates_epoch_no_update BEFORE UPDATE ON candidates_immutability_epoch ...
CREATE TRIGGER trg_candidates_epoch_no_delete BEFORE DELETE ON candidates_immutability_epoch ...
CREATE TRIGGER trg_candidates_epoch_no_insert BEFORE INSERT ON candidates_immutability_epoch ...
```

> **A TWO-TRIGGER EPOCH IS FAIL-OPEN AT SQLITE'S DEFAULT, AND I VERIFIED IT BY EXECUTION RATHER
> THAN BY READING THIS PLAN.** The previous specification was UPDATE + DELETE triggers, and S4.5C
> asserted that ``INSERT OR REPLACE`` *"aborts at the DELETE half."* **It does not.** For the
> `REPLACE` conflict-resolution strategy SQLite fires DELETE triggers **if and only if
> `PRAGMA recursive_triggers` is ON**, and it is **OFF by default**. Measured on sqlite 3.50.4:
>
> | statement | two triggers, `recursive_triggers` OFF (production) | three triggers, OFF |
> |---|---|---|
> | `UPDATE` | aborts | aborts |
> | `DELETE` | aborts | aborts |
> | `INSERT` `epoch_id=2` | aborts (the `CHECK`) | aborts |
> | `INSERT OR REPLACE` `epoch_id=1` | **SUCCEEDS -- row silently rewritten** | aborts |
> | bare `REPLACE` / `INSERT OR IGNORE` | **SUCCEEDS** | aborts |
>
> **AND THE REPO DOES NOT ENABLE IT.** `grep -rn 'recursive_triggers' swing/ tests/` returns **zero
> hits**; `swing/data/db.py:118-121` sets `busy_timeout`, `foreign_keys=ON` and `journal_mode=WAL`
> and nothing else. **So the default governs in production**, and case 35c as previously written
> asserted behaviour SQLite does not have -- it would have failed, and the two ways to make it pass
> are to enable a global pragma (a connection-wide semantic change, far outside this envelope) or
> to quietly drop the case.
>
> **THIS IS THE FAIL-OPEN DIRECTION, WHICH S4.5B ITSELF SAYS CANNOT BE TOLERATED:** an
> `INSERT OR REPLACE` LOWERING `max_candidate_id_at_barrier` stamps a **PRE-barrier fire
> `live_at_acceptance`** -- a false structural-proof label minted by the mechanism that exists to
> make the proof honest.
>
> **THE FIX IS A THIRD TRIGGER, `BEFORE INSERT`, CREATED AFTER THE SEEDING ROW.** It refuses every
> subsequent INSERT of any conflict-resolution flavour, because the INSERT half always fires its
> own triggers. `epoch_id INTEGER PRIMARY KEY CHECK (epoch_id = 1)` is kept as the declarative belt
> -- it alone stops a plain second-row insert -- but **the trigger is the load-bearing half, and a
> `CHECK` cannot substitute for it** because `REPLACE` satisfies the `CHECK` by deleting the row
> that conflicts with it.
>
> **CONSEQUENCE FOR THE CARVE, STATED PLAINLY: the third epoch trigger does NOT fall away.** What
> falls away is the trigger CHARC approved -- the one guarding an ERA SEQUENCE (a lower re-arm
> after a retirement), which single-state cannot represent. **A different third trigger takes its
> place, at the same COUNT and on the same CONDITION-4 footing** (purely additive: nothing rebuilt,
> nothing dropped, no existing row touched). **The count he ruled on is unchanged; the third
> trigger's PURPOSE is not, and that is surfaced at his section-3 gate as a change of substance
> rather than absorbed** -- S4.5B.
>
> **CONDITION 3 IS UNAFFECTED and is in fact better served:** retirement is no longer recorded by
> appending a row to this table (that was the ERA LEDGER, carved), so **the INSERT barrier is now
> AVAILABLE where CONDITION 3 previously forbade it.** A drop is recorded by the numbered migration
> that performs it, and its CONSEQUENCE is mechanical via the `sqlite_master` existence check
> (S2.4d.1) rather than via a ledger row nobody is compelled to write.
>
> **Cases 35a-35c, 35n, 35p** -- `UPDATE`; `DELETE`; **`INSERT OR REPLACE`**; a plain second-row
> `INSERT` with `epoch_id=2`; and **bare `REPLACE` plus `INSERT OR IGNORE`** -- each must ABORT
> **with `recursive_triggers` left at its default, which every test must assert rather than set.**
> *(The ids skip `35d`-`35m`: those assert ERA behaviour and travel to 22-A2.)* **A two-trigger
> implementation passes 35a, 35b and 35n and FAILS 35c and 35p**, which is the discriminator.

### S4.5A CHARC'S FOUR BINDING CONDITIONS (ruling 2026-08-24), each encoded at its site

**The barrier is APPROVED, UPDATE and DELETE both** -- the DELETE half being load-bearing exactly
as review 22A-R15-02 argued: `candidates.id` is a reusable rowid, and a deleted-and-reused id would
silently repoint every citation at a different row (the `fills.fill_id`-reuse class).

* **CONDITION 1 -- A FULL LIVE PIPELINE RUN IS A PRE-MERGE GATE, not a recommendation.** Both
  directors made it binding. *The residual risk is availability; the nightly is the only instrument
  that converts "no writer visible" into "no writer on the paths the nightly exercises."* Encoded
  as **S9 step 0**, which runs BEFORE the correction and blocks the merge on its own. It is a gate
  and not a smoke test: a `RAISE(ABORT)` from either trigger during `_step_evaluate`,
  `_step_finviz_fetch`, `_step_ohlcv` or any downstream step is a STOP, and the arc returns to
  CHARC rather than the trigger being relaxed.
* **CONDITION 2 -- THE REFUSAL MUST BE LEGIBLE AND NAMED.** *A refusal that does not say what to do
  next is a dead end, not a guard.* Both `RAISE(ABORT)` messages name the BARRIER, the ARC, and the
  RECOVERY PATH, verbatim:

  ```
  22-A barrier trg_candidates_no_update: candidates rows are IMMUTABLE from migration 0037.
  A re-evaluation APPENDS a new row; it never edits an existing one. To change a fire's
  recorded values you must add an evaluation run. To retire the barrier see the reversibility
  header of 0037_latch_order_mandate_links.sql.

  22-A barrier trg_candidates_no_delete: candidates rows are PERMANENT from migration 0037.
  The latch identity space and every provenance citation address rows by a REUSABLE rowid, so
  a delete would silently repoint them. Pruning is a migration-level operation -- see the
  reversibility header of 0037_latch_order_mandate_links.sql.
  ```

  A test asserts each message contains the trigger name, the string `22-A`, and the words
  `reversibility header` -- **asserted as content, not as an exact byte-string**, so the message can
  be improved without a false red.
* **CONDITION 3 -- REVERSIBILITY STATED IN THE MIGRATION'S OWN HEADER.** The header of `0037` says,
  in a comment block that is part of the migration file: the barrier is retired by exactly two
  statements, `DROP TRIGGER trg_candidates_no_update;` and `DROP TRIGGER trg_candidates_no_delete;`
  -- **and, because dropping ENDS the proven guarantee rather than falsifying it, any drop must
  itself be RECORDED.** The plan says how: a drop is performed only inside a NEW numbered
  migration, which is itself the record.

  > **UNDER OPTION C THE RECORDING IS MECHANICAL, NOT PROCEDURAL -- and that is what CHARC required
  > (S2.4d.1).** This condition previously required the retiring migration to **append a second row
  > to `candidates_immutability_epoch`** marking `barrier_state='retired'`, with every later reader
  > treating a post-`retired` fire as pre-barrier again. **That is the ERA LEDGER, and it is CARVED
  > to 22-A2 with the era model it belongs to (S12).** What replaces it is strictly stronger for
  > this arc's purpose: **the admission reader verifies both barrier triggers EXIST at read time
  > and refuses `barrier_not_installed` if either is absent**, so a drop halts structural admission
  > whether or not anyone remembered to record it. *An era ledger that cannot record its own end is
  > not a ledger -- but a reader that checks the guarantee is still standing does not need one.*
  >
  > **AND THIS IS WHAT FREES THE EPOCH'S INSERT BARRIER.** CONDITION 3 previously required INSERT
  > to stay OPEN so retirement could be appended. With retirement no longer written here,
  > **INSERT can be closed absolutely** -- which S4.5-epoch shows is not optional, because
  > `INSERT OR REPLACE` is otherwise a measured fail-open path to a false structural-proof label.
* **CONDITION 4 -- THE MIGRATION IS ADDITIVE.** Nothing rebuilt, nothing dropped, no existing row
  touched. The barrier's footprint is `CREATE TRIGGER` x2 on `candidates` + the one-row epoch table
  + the version bump, exactly as enumerated. **The plan finds it needs THREE MORE `CREATE TRIGGER`s
  than that -- on the epoch table -- and routed rather than took them. BOTH exceptions are now
  RULED AND APPROVED: S4.5B.**

### S4.5B THE TWO CONDITION-4 EXCEPTIONS -- **BOTH RULED AND APPROVED (CHARC, 2026-08-24)**

> **THE INTENT OF CONDITION 4, NOW STATED BY ITS AUTHOR SO THIS CLASS IS NEVER ROUTED AGAIN:**
> *"A transactional DROP+CREATE that replaces a guard with an EQUAL-OR-STRONGER guard is not a DROP
> in Condition-4's sense -- but it is ALWAYS DECLARED, NEVER SILENT."* The condition's WORD was
> "nothing dropped"; its INTENT was **no destruction of data or of a standing guarantee.** Declining
> to guess which was meant was the right call, and the adjudication now lives in the plan and in the
> migration header rather than in a reader's inference.

**EXCEPTION 1 -- the epoch's THIRD trigger: APPROVED.** Three `CREATE TRIGGER`s meet CONDITION 4's
criterion exactly as two did -- nothing rebuilt, nothing dropped, no existing row touched -- **so
the count moving is not a widening of the condition's KIND.** Task 2 is UNBLOCKED.

> **THE APPROVED COUNT SURVIVES THE CARVE; THE THIRD TRIGGER'S IDENTITY DOES NOT, AND THAT IS
> SURFACED RATHER THAN ABSORBED (2026-08-24, post-carve).** CHARC ruled on **three** epoch triggers
> where the third guarded an **ERA SEQUENCE** -- a permitted `armed` INSERT after a `retired` row
> carrying a boundary BELOW the unbarriered era's candidates (review 22A-R5-01). **Single-state
> models no eras, so that trigger's threat is not representable in this arc and it travels to
> 22-A2.** But the epoch still needs a third trigger, for a DIFFERENT and independently measured
> reason: **`BEFORE INSERT`, closing an `INSERT OR REPLACE` rewrite that is OPEN at SQLite's
> default `recursive_triggers=OFF`, which this repo never enables** (S4.5-epoch, verified by
> execution on sqlite 3.50.4 and by `grep -rn 'recursive_triggers' swing/ tests/` returning zero).
> **The count he approved (three) and the criterion he approved it on (purely additive) are both
> unchanged.** What changed is which hole the third one plugs -- **stated here so his section-3
> gate re-reads it rather than inheriting an approval given for another purpose.**

**AND THE APPROVAL CARRIES A NEW OBLIGATION, which is the honest consequence of the approval:** the
third trigger's property was listed under "clauses with NO case" on the ground that it was
untestable **if declined**. It was not declined, **so it is testable, so it must BE tested** --
**cases 35c and 35p** (`INSERT OR REPLACE`; bare `REPLACE` and `INSERT OR IGNORE`), each asserted
with `recursive_triggers` left at its default. *(CHARC's own specified case 35g -- create
candidates inside a retired window, re-arm, assert they are NOT stamped `live_at_acceptance` --
tests the ERA trigger and travels to 22-A2 with it.)* **A two-trigger implementation fails 35c and
35p and passes everything else in this plan.**

**EXCEPTION 2 -- the `provenance_corrections` trigger replacement: APPROVED**, under three
requirements, each encoded at its site:

* **(a) DROP and CREATE inside the SAME explicit `BEGIN`/`COMMIT`** (gotcha #9 -- `executescript`
  issues an implicit COMMIT and runs in autocommit, so a naive migration would leave a window in
  which `provenance_corrections` sits with NO append-only guard at all). The migration's explicit
  transaction wraps both statements for both triggers; a test asserts the migration file contains no
  statement between the DROP and its CREATE.
* **(b) The plan carries the before/after trigger-body DIFF, and the accept proves the OLD
  guarantee SURVIVES.** S4.3 shows the diff. **The test is computed against the OLD guarantee, not
  against the new features:** for every column the PRE-0037 trigger protected, a barred write must
  STILL fail post-migration. **This is the discriminating half** -- a test written only against the
  six new columns passes a replacement that silently dropped protection on an old one.
* **(c) The migration header NAMES this ruling** as the explicit exception, so the next reader of
  "nothing dropped" finds the adjudication instead of the ambiguity.

### S4.5B-hist THE ROUTING RECORD (kept, because the routing is why both were adjudicated)

CHARC's CONDITION 4 said: *"If the plan finds it needs more than that, STOP and route back to me
before continuing."* It did, in **TWO** places -- and my previous draft claimed *"in exactly one
place"* while S0.1 openly acknowledged the second three pages earlier (review 22A-R5-10). **Both
were routed rather than taken; both are now APPROVED (S4.5B above), and Tasks 2 and 11 are
UNBLOCKED.** The record below is kept because the routing is the reason the adjudication exists.

**EXCEPTION 2, stated first because it is the one I had already half-admitted: the migration DROPS
two triggers.** `S4.3` requires `DROP TRIGGER` + `CREATE TRIGGER` for
`trg_provenance_corrections_citation_graph` and `trg_provenance_corrections_append_only_update`,
because SQLite has no `ALTER TRIGGER` and both must learn six new columns. Under CONDITION 4's
literal text -- *"nothing dropped"* -- that is a violation, twice, inside one transaction, with the
replacements created immediately. **The alternative is rebuilding the audit table of record (the
D30 class) or leaving the new columns freely rewritable on an append-only table, which is worse
than either.** **Asked of CHARC: either route the replacement as an explicit second CONDITION-4
exception, or clarify that "nothing dropped" excludes the transactional replacement of a trigger
DEFINITION.** I am not going to decide which he meant.

**THE ASK: THREE additional `CREATE TRIGGER`s, on `candidates_immutability_epoch`** (the count
moved from two after review 22A-R5-01 -- see "THREE, NOT TWO" below).

```sql
CREATE TRIGGER trg_candidates_epoch_no_update BEFORE UPDATE ON candidates_immutability_epoch
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_candidates_epoch_no_update: the immutability epoch is
  written ONCE by migration 0037 and never again. ...'); END;
CREATE TRIGGER trg_candidates_epoch_no_delete BEFORE DELETE ON candidates_immutability_epoch
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_candidates_epoch_no_delete: ...'); END;
CREATE TRIGGER trg_candidates_epoch_no_insert BEFORE INSERT ON candidates_immutability_epoch
BEGIN SELECT RAISE(ABORT, '22-A barrier trg_candidates_epoch_no_insert: ...'); END;
-- created AFTER the seeding INSERT, in the same transaction (S4.5-epoch)
```

**Why (review 22A-R3-07), and why the direction of the failure decides it.** The epoch row is what
the minting trigger consults to stamp `freeze_tier`. As specified it is freely mutable. **Raising**
`max_candidate_id_at_barrier` mis-stamps post-barrier fires as `pre_barrier_reconstructed`, which
under RD's refuse-by-default costs an admission -- fail-closed, survivable. **LOWERING it stamps a
PRE-barrier fire `live_at_acceptance`: a FALSE PROOF LABEL, minted by the very mechanism that
exists to make the proof honest, and fail-OPEN.** That is why this cannot be left as a declared
limitation the way R3-08 can.

**THREE, NOT TWO -- and the third has now been arrived at TWICE, from two unrelated directions,
which is the strongest argument the number is right.** *(Historically, review 22A-R5-01: CONDITION
3 required INSERT to stay OPEN because retirement was recorded by appending a row, so a permitted
`armed` INSERT after a `retired` row could carry a boundary BELOW the unbarriered era's candidates
and stamp them `live_at_acceptance`. A `CHECK` cannot bind a column to `MAX(candidates.id)` --
cross-table -- so a trigger was not a preference. **That reasoning is the ERA model's and travels
to 22-A2.**)*

**UNDER SINGLE-STATE THE THIRD TRIGGER IS RE-DERIVED ON ITS OWN GROUND (S4.5-epoch).** Retirement is
no longer written to this table, so INSERT may be closed absolutely -- and it MUST be, because
`INSERT OR REPLACE` bypasses a DELETE trigger whenever `PRAGMA recursive_triggers` is OFF, which is
SQLite's default and this repo's actual state. **Both derivations land on the same statement count
and the same purely-additive footprint** (`0033:834-837` shape; nothing rebuilt, nothing dropped, no
existing row touched), which is why the ruling's terms still hold.

**I am stating the revision rather than quietly re-scoping the ask**, because a routed number that
moves between the routing and the ruling is worse than a larger number stated once.
**The SPIRIT of CONDITION 4 is preserved; its LETTER is exceeded by two statements, and I am not
going to take that silently.**

**If CHARC declines the third trigger**, the plan does NOT proceed as written. The fallback is
stated so the decision is a real choice: drop `candidates_immutability_epoch` entirely and mint
EVERY link `pre_barrier_reconstructed` until a later arc supplies a creation-time marker that is
not inferred from a rewritable row -- which, under RD's refuse-by-default, means the entry path admits nothing
structurally and the arc's stop-the-bleeding value waits on that arc. That is a materially
different arc and it goes back to CHARC as one.

**A SECOND, SEPARABLE ASK, listed so it is not smuggled in with the first: `candidate_criteria`
immutability** (S2.6.5, review 22A-R3-09) -- two more `CREATE TRIGGER`s on a THIRD table.
**This plan does NOT request it and proceeds WITHOUT it**, carrying the exposure as **L13** with a
detection-only mitigation, because the label suffix is cohort bookkeeping rather than the
money-bearing comparison and the arc can be honest about it. It is named here only so CHARC sees
the whole surface at once and can pull it forward if he disagrees with that judgment.

### S4.5C THE EPOCH IS READ IN EXACTLY ONE PLACE (CHARC's ruling, lifted verbatim into the design)

> Rows whose fire predates the epoch do not admit structurally; rows at or after it do. **ONE
> reader, no date arithmetic scattered through call sites** -- the same single-authority shape as
> `cohort_intent`.

*(CHARC's ruling as delivered read "...predates the epoch admit only through RD's tier-2 class."
**The tier-2 class is CARVED to 22-A2, so under Option C a pre-barrier row admits through nothing
at all** -- RD's refuse-by-default taken at its word, S2.4d. The ruling's operative half -- ONE
reader -- is unchanged and is what the section encodes.)*

Encoded as `swing/data/repos/candidates_immutability_epoch.py::freeze_tier_for_candidate(conn,
candidate_id) -> (tier, barrier_installed)`. **It is the ONLY module that reads the epoch table AND
the only one that performs the `sqlite_master` existence check (S2.4d.1)** -- so no call site does
era arithmetic and none writes its own trigger-existence query. The minting trigger's `CASE` is its
SQL twin and is the only other site that may embed the boundary comparison; a test greps `swing/`
for `max_candidate_id_at_barrier` and for `sqlite_master` and asserts exactly those hits plus the
migration. **A second test runs the Python reader and the SQL twin over the same fixtures and
asserts they agree** -- two spellings of one rule is the D6 class, and only a test that runs both
can see it. **The fixtures are single-state** -- a candidate below the boundary, one at it, one
above -- **not the armed/retired/re-armed sequences case 38 previously ran**, which are era shapes
this arc cannot construct (S12).


**Tests:** an UPDATE aborts; a DELETE aborts; **each abort message names its trigger, `22-A`, and
`reversibility header`** (CONDITION 2, asserted as content); `insert_candidates` still works; the
pipeline `_step_evaluate` path still works; `run_migrations` twice is a no-op and **does not
re-stamp the epoch -- which is now enforced by the `BEFORE INSERT` trigger rather than only by the
version gate, so a re-seed ABORTS loudly instead of silently succeeding**; **a pre-0037 candidate
receiving its FIRST acceptance AFTER 0037 mints `pre_barrier_reconstructed`** (the RHI shape); a
post-0037 candidate mints `live_at_acceptance`; **and the epoch table refuses EVERY write path with
`recursive_triggers` left at its default** -- `UPDATE` (35a), `DELETE` (35b), `INSERT OR REPLACE`
(35c), a plain second-row `INSERT` (35n), bare `REPLACE` and `INSERT OR IGNORE` (35p), per
S4.5-epoch. **Each test asserts the pragma default rather than setting it**, because a test that
sets `recursive_triggers=ON` proves the trigger fires in a world production is not in.

**AND THE `-pre`/ERA CASES ARE GONE WITH THE MODEL:** 35d (a schema-valid era sequence tiering each
era correctly), 35e (an appended `retired` row making later fires pre-barrier again) and 35f/35g
(the spurious lower re-arm) **all assert ERA behaviour that single-state cannot represent, and they
travel to 22-A2** (S12). *(They are struck here rather than left as "conditional on the ruling":
the ruling landed, and a case list that still names them would have an executor building the era
columns to make them constructable.)*
**Interaction with cases 9/9b:** the drift cases must plant their mutation by dropping the trigger
inside the test transaction -- the resolver's cross-check must not depend on the barrier, because
pre-barrier rows exist and a future migration could rebuild the table.

---

## S5. MODULES

### S5.1 `swing/trades/latched_origin.py` (NEW)

```
SCHWAB_ORDER_ID_ENVELOPE_KEY = "schwab_order_id"   # imported by entry_auto_fill.py's writer
TRUSTED_LATCH_FILL_ORIGINS = frozenset({"schwab_auto", "schwab_auto_then_operator_corrected"})

class LatchProbeInvariantError(RuntimeError): ...

@dataclass(frozen=True)
class AcceptedLatchOrder:
    link_id: int; validity_intent_id: int; place_intent_id: int; candidate_id: int
    evaluation_run_id: int; ticker: str; detection_date: str; broker_order_id: str
    frozen_pivot: float | None; frozen_invalidation: float | None
    actual_quantity: int | None; freeze_tier: str   # NO cap: derived from frozen_pivot at read time
    actual_limit_price: float | None                # the ACCEPTED order's own limit (review 22A-R8-07)

@dataclass(frozen=True)
class LatchedProvenance:
    admitted: bool
    recognised_but_underivable: bool
    decline_reason: str | None
    order: AcceptedLatchOrder | None
    clear_reason: str | None; clear_session: date | None
    horizon_session: date | None   # = the fill session; SQL-BOUND in the evidence blob
    bars_through: date | None      # = the derivation's prior exchange session; service-validated
    window_empty: bool; archive_status: str | None
    trade_origin: str | None; candidate_id: int | None; hypothesis_label: str | None
    probe_evidence: dict           # frozen verbatim into cited_latch_probe_json
    freeze_tier: str | None        # rung 9's subject; NEVER inferred from the acceptance time

def broker_order_id_from_envelope(raw: str | None) -> str | None
def find_accepted_latch_order(conn, *, broker_order_id) -> list[AcceptedLatchOrder]
    # SELECTs v.actual_limit_price through the existing validity JOIN -- see below
def authorize_accepted_order(conn, cfg, *, order, ticker, fill_session, price, shares,
                             fill_origin, exclude_trade_ids) -> LatchedProvenance
def assert_fill_consistent_with_order(order, *, ticker, price, shares, fill_origin) -> str | None
def mandate_alive_at(conn, cfg, *, order, fill_session, exclude_trade_ids) -> LatchedProvenance
def resolve_latched_provenance(conn, cfg, req) -> LatchedProvenance
```

Decline reasons, each with a case in S3.7 -- **THIRTY-THREE, counted by tokenising the fenced block
below and counting the distinct members, never by grepping for the word `refuse`.** *(Re-counted
after the Option-C carve, which removed four tier-2 reasons: 37 -> 33.)* **A worked illustration of
why the method has to be stated, kept because it is instructive even though its subject is now
carved:** the roster used to contain `tier2_evidence_unverified`, and a `^[a-z_]+$` regex over the
block returned one FEWER than the read **because that member contains a digit** -- a regex
under-counting a roster in the very act of fixing an under-count, the exact failure CLAUDE.md
records for the item-5 mirror set. *(The digit-bearing member left with the tier-2 class, so that
particular regex would agree today -- which is precisely why the anecdote is worth keeping and the
regex is not: the next member with a digit will not announce itself.)* That read found THREE reasons my previous draft had specified in
prose (S2.3.3b, S2.3.4b) and never added to the frozenset -- `decision_evidence_unavailable`,
`decision_evidence_post_dates_fill`, `decision_ordering_ambiguous` -- **which is the closure hole
the closure test exists to catch, found by reading rather than by matching:**

```
no_config                            no_envelope
no_order_id                          untrusted_fill_origin
no_accepted_latch_order              ambiguous_accepted_orders
linked_validity_not_accepted         quantity_exceeds_order
ambiguous_ticker_orders              competitor_liveness_unverifiable
validity_superseded                  place_cycle_superseded
link_parent_incoherent               order_cancelled
cancel_ordering_ambiguous            ticker_mismatch
fill_outside_frozen_zone             link_field_unbound
mandate_already_consumed             consumption_evidence_unavailable
fill_session_not_a_session           fire_not_derivable
ambiguous_fire_membership            frozen_value_unavailable
frozen_value_drift                   pre_barrier_unproven
aliveness_unverifiable               mandate_not_alive
keys_not_derivable                   decision_evidence_unavailable
decision_evidence_post_dates_fill    decision_ordering_ambiguous
barrier_not_installed
```

**A test enumerates this frozenset and asserts every member is exercised by a named case** -- the
closure check, so the roster cannot quietly grow a member nothing covers. **And per the recipe's
roster lesson, the list is not the fix: a SECOND test walks the module's own `raise`/return sites
statically and asserts every reason string it constructs is a member** -- a maintained list fails
the same way as the count it replaced.

**THE PLAN CLAIMED "each with a case in S3.7" AND DID NOT ESTABLISH IT (SELF-SWEEP SS-10).** I ran
the closure check the plan prescribes against the plan itself, by READ: **eighteen of the
thirty-three reasons were not named anywhere in the lens table, and SEVEN appeared exactly ONCE in
the entire document -- inside this roster.** Most were genuinely covered by a case whose row simply
did not NAME the reason, which is the difference between covered and CHECKABLE. **Three were not
covered at all**, and one was DEAD. This is the "hand-enumerated roster fails the same way as the
count it replaced" lesson landing on the very roster written to satisfy it.

**The fix is the REASON VIEW below, built by reading each reason and finding its case** -- the lens
table is the CLAUSE view and answers a different question. A reason with no case is now visible as
a blank rather than as an unstated assumption.

| reason | case(s) |
|---|---|
| `no_config`, `no_order_id` | 18 |
| `no_envelope` | 15e |
| `untrusted_fill_origin` | 15a |
| `no_accepted_latch_order` | 2, 4 |
| `ambiguous_accepted_orders` | 14 |
| `linked_validity_not_accepted` | 4d(i) |
| `quantity_exceeds_order` | 15d-ii |
| `ambiguous_ticker_orders` | 4c-ii, 15f |
| `competitor_liveness_unverifiable` | 23b-23d |
| `validity_superseded` | 4d(ii) |
| `place_cycle_superseded` | 29a |
| `link_parent_incoherent` | **41a (NEW -- had NO case)** |
| `order_cancelled` | 29b |
| `cancel_ordering_ambiguous` | 29c |
| `ticker_mismatch` | 15c |
| `fill_outside_frozen_zone` | 15b, 30a, 30c |
| `mandate_already_consumed` | 13 |
| `consumption_evidence_unavailable` | 22b |
| `fill_session_not_a_session` | **41b (NEW -- S2.4.2 CITED case 5c, which is the corrected-DATE discriminator and does not exercise a non-session anchor at all: a mis-cited case reads exactly like a covered one)** |
| `fire_not_derivable` | **41c (NEW -- case 27 only asserts that a WRONG implementation produces it; no case had the CORRECT implementation produce it, e.g. a probe as-of before the fire, S1.9)** |
| `ambiguous_fire_membership` | **41d (NEW -- introduced by the R3-06 fix and never given a case: two latches containing the same fire)** |
| `frozen_value_unavailable` | **41e (NEW -- the junk-pivot link mints NULL frozen values (S4.2); no case carried it through to the RESOLVER's refusal)** |
| `frozen_value_drift` | 9, 9b |
| `pre_barrier_unproven` | every `-pre` twin; **1-pre, which under Option C is trade 25's LIVE outcome rather than a twin** |
| `barrier_not_installed` | **50a-50c (NEW, CHARC 2026-08-24)** -- the `sqlite_master` existence check: both barrier triggers present -> ADMIT; either dropped -> REFUSE **even for a post-barrier fire** |
| `link_field_unbound` | **47a-47c (NEW, review 22A-R7-04)** -- a raw link substituting the broker order id; inflating the quantity; naming a different ticker |
| `aliveness_unverifiable` | 7, 7b |
| `mandate_not_alive` | 5, 28f |
| `keys_not_derivable` | 12 |
| `decision_evidence_unavailable` | 19 |
| `decision_evidence_post_dates_fill`, `decision_ordering_ambiguous` | 20 |

**`quantity_mismatch` was DELETED from the roster** (SELF-SWEEP SS-06): review 22A-R5-04 replaced
the equality rung with `0 < shares <= actual_quantity`, so an UNDER-quantity now ADMITS and the
over-quantity direction refuses `quantity_exceeds_order`. **Nothing could produce
`quantity_mismatch` any more, and a reason no rung can emit is a roster member whose case would
have had to be written against dead code.** *(That deletion moved the roster 33 -> 32 at the time;
later rounds and then the Option-C carve moved it again. **The current figure is the THIRTY-THREE
counted above, and this line records a deletion, not the total** -- a running arithmetic left beside
a stated count reads as a contradiction of it.)*

**THE LOOKUP AND THE AUTHORIZATION ARE TWO FUNCTIONS, because the declared one-argument signature
could not implement the (then nine, now ELEVEN) rungs assigned to it (review 22A-R4-08).** `find_accepted_latch_order`
is a RAW lookup: it takes a broker order id and returns **the LIST of matching links** -- returning
a list rather than an Optional is what makes S2.4's "cardinality by COUNT, not `fetchone()`"
expressible in the type instead of only in prose. Every contextual rung (ticker, governing place,
cancellation ordering, consumption, competitor liveness, freeze tier) needs `cfg`, the fill session,
the request fields and the exclusion set, and those live on `authorize_accepted_order`. **All ELEVEN rungs live on the second function; the
first has no rungs at all.** They ship across TWO tasks -- **task 4 lands ten (1, 2, 3, 3b, 3c, 4,
5, 6, 7, 9) and task 6a lands rung 8**, which cannot run until `mandate_alive_at` exists (22A-R7-09,
corrected at 22A-R8-08: the previous text said task 4 assigned "ALL TEN", which was two errors in
three words -- the count was eleven and the assignment was split). My previous draft gave
one function a one-argument signature and nine context-dependent rungs, which an implementer could
only reconcile by hiding inputs or dropping rungs.

`broker_order_id_from_envelope` returns `None` (never raises) on malformed JSON, non-dict, missing
key, non-string or empty value, logging at WARNING when the JSON is present but unusable -- the
graceful-degrade posture for a read-only consumer. The key name is imported from ONE constant used
by the writer at `entry_auto_fill.py:470`, never re-spelled (#11). `trade_origin` comes from
`swing.metrics.funnel.APLUS_TRADE_ORIGIN`, never a third spelling of the literal.

### S5.2-S5.5

* `swing/trades/cohort_provenance_correction.py`: rungs 16-18 extracted (S2.6.1); `_authorize`
  resolves the tier before the last-word guard and dispatches (S2.7); preview/result carry the tier
  and citations; the scope-boundary comment at the dispatch site.
* `swing/trades/entry.py`: `cfg=None`; the override block after the gauntlet (S2.2); WARNING logs.
* `swing/latches/reader.py` (EXT-1): THREE keyword-only parameters -- `criteria_lapse_armed_override`
  (threaded to `derive_latches`' existing argument; `None` preserves today's `getattr` read exactly), `exclude_trade_ids` (filters `load_entry_records`' output), and `strict_decisions` (makes `load_decision_intents` raise rather than return `{}`).
* `swing/web/routes/trades.py` (EXT-2): the hidden-envelope ladder gains a `schwab_order_id` shape
  rung, and tier-(e) consults the resolver with **its behaviour specified for all
THREE outcomes (review 22A-R15-14), because "consult the resolver" left the most dangerous one
undefined**: (a) no recognised link + server origin manual -> reject exactly as today; (b)
recognised AND admitted -> pass through; (c) **recognised AND REFUSED** (invalidation, drift,
coverage, key derivation) -> **pass through, do NOT reject**. Rejecting (c) at the route would
block a money-bearing entry over cohort bookkeeping -- the `0036:26-38` inversion -- when the
service's correct answer is the honest-unset row.

**AND THE ROUTE'S OWN CONNECTION LIFECYCLE FALSIFIED THE ATOMICITY CLAIM (review 22A-R7-10).** The
shipped tier-(e) guard opens a connection, computes its rejection verdict, CLOSES it, and only later
opens a SECOND connection for `record_entry` (`swing/web/routes/trades.py:1261`, `:1371`). **So the
route can observe "no link + manual origin", reject, and never reach the authoritative transaction
at all -- even if a matching link lands immediately afterwards.** S2.2's `BEGIN IMMEDIATE` closes
the no-link->link race INSIDE `record_entry` and does nothing for this one, and **case 21b tests the
service race, not the route race** -- so the plan's atomicity claim was true of the service and
false of the approved production path, which is the only path the operator uses.

**THE FIX: the route STOPS deciding -- AND THE GUARD IT STOPS APPLYING IS RELOCATED, NOT DELETED
(review 22A-R9-03).** EXT-2(a) already routes tier-(e) through the resolver; **this narrows it
further -- for any request carrying a usable broker order id, the route performs NO origin-based
rejection at all and defers the entire decision (PE-anchor guard AND latch authority) to
`record_entry`, inside the one transaction that also writes.** A request with no usable order id
keeps today's route behaviour byte-for-byte, so the LOCK's scope is unchanged.

> ### **DEFERRING A DECISION IS NOT THE SAME AS MOVING IT, AND MY PREVIOUS DRAFT DID THE FIRST WHILE
> CLAIMING THE SECOND (review 22A-R9-03 -- a CRITICAL, and it removes a LIVE production rejection).**
>
> **The PE-anchor / manual-origin rejection exists in exactly ONE place: the route.**
> `swing/web/routes/trades.py:1261-1268` opens its own connection, calls `derive_trade_origin`, and
> **rejects when the server-derived origin is `manual_off_pipeline`** while a `pattern_evaluation_id`
> anchor is present. **`record_entry` has NO equivalent rejection** -- its ordinary no-link path
> simply derives and persists the ordinary result (`swing/trades/entry.py:264`, `:352-373`).
>
> **So "the route decides nothing" as written DELETES the guard.** A request carrying (a) a usable
> but UNMATCHED broker order id, (b) a `pattern_evaluation_id`, and (c) a manual latest-run origin
> skips the route rejection, resolves down the ordinary no-link path, **and is WRITTEN. Today it is
> REJECTED.** That is a live behaviour regression introduced by a fix for a race.
>
> **And case 37b does not catch it: 37b plants a link that ARRIVES**, so it exercises the race, not
> the stable no-link outcome -- **the very "tests the admitted branch only" shape this section
> already corrected once for tier-(e).**
>
> **THE RELOCATION, stated as an obligation on the task rather than as a consequence of deferral:**
> **`record_entry` GAINS the PE-anchor guard**, evaluated INSIDE the `BEGIN IMMEDIATE` transaction,
> after latch resolution and before the INSERT: *if the request carries a `pattern_evaluation_id`
> anchor AND latch resolution did not admit AND the server-derived origin is
> `manual_off_pipeline`, REFUSE the entry* -- the same refusal the route makes today, with the same
> operator-facing message, now made once and at the authoritative moment. **The route's copy is
> removed only for order-id-bearing requests, and only because the service now holds it.**
>
> **Why inside the transaction is the whole point:** the guard's input is `derive_trade_origin`,
> which reads the latest evaluation run -- the same world the race can move. Evaluated at the route
> it reads a world that may be stale by the time the row is written; evaluated inside
> `BEGIN IMMEDIATE` it reads the world the write lands in.
>
> **Case 37c (NEW): the STABLE no-link outcome.** A request with a usable-but-unmatched order id, a
> `pattern_evaluation_id`, and manual latest-run origin, **with no link arriving at any point** ->
> **REFUSED, by the service, with the PE-anchor message.** *An implementation that defers the route
> guard without relocating it WRITES the row and passes 37, 37b and every other case in this plan.*
> **This is the discriminating case, and it is task 9's, not task 10's** -- the guard lands in
> `record_entry`.

**Case 37b: a route-level no-link->link race** -- a link lands between the route's read and the
service's transaction; the written row must reflect the INSIDE verdict. **An implementation keeping
the route's own connection fails it, and passes every other case in this plan.**

**A route test also covers a
recognised-but-INVALIDATED fill whose latest-run origin has drifted to manual (case 37, harvest H5
from round 2a 22A-REV-12's sibling finding).** My previous Task-10 acceptance said only *"route and
service agree on a latched-with-PE-anchor entry"*, which names the ADMITTED branch and passes an
implementation that still rejects (c) at the route -- and (c) is the branch where a money-bearing
entry would be blocked over cohort bookkeeping. **Both branches are named in the acceptance, not
one.**

---

## S6. TEST DESIGN

The six binding cases (S3.1-S3.6) plus S3.7's lens: **EIGHTY table rows, of which TWO are struck as
REMOVED (`11b` and `54`), so SEVENTY-EIGHT LIVE CLAUSE ROWS.** *(Method, because a bare "80" hides
the distinction that matters: count the lines beginning `|` between the S3.7 and S3.8 headings --
**82** -- subtract the header and separator, then subtract the struck rows. Re-run at the round-9
pass, when the `54` strike was added; zero duplicate ids.)* Down from 96 before the Option-C carve
-- **and I got this wrong by one on the first attempt in an earlier pass (EC-3),
which is the sixth instance of the count family in this loop and the third that was mine.** The
number is a mechanical read of the table, re-run after the last row landed (sub-labelled `9b`, `13c`, `38b` and so on). **Both figures are re-READ at this
sweep and both had moved** -- the previous "sixty-three rows / 1-45" was correct when written and
was falsified by the twelve rows rounds 4-5 and this sweep added, which is the same
count-goes-stale shape three times over. **The count is stated with the method,
and the method matters here because my first attempt at it was WRONG in the ordinary way:** I wrote
"forty-five clause rows", which is the highest clause NUMBER, not the number of rows -- the two
differ by every sub-label. Counted by reading the table. **Note also that a clause row is not a
case:** some rows name several cases, and several rows share one. Plus:

* **Demand-C non-regression:** the entire existing suite green unchanged; the CADL golden; a test
  that the unlatched path still calls `_assert_last_word_before_the_fill`.
* **Trade-25 end-to-end** through the extended surface on a fixture built from trade 25's real
  rows -- **and under Option C it has exactly ONE run and ONE outcome: REFUSED
  `pre_barrier_unproven`, keys honestly NULL, the pending-label row intact.** *(It was a TWO-run
  tier-2 case -- without the evidence flag refuse, with it admit at `latch_ladder_tier2`. Both the
  flag and the tier are CARVED to 22-A2, so the second run is not constructable here.)*
  **`latch_ladder` is reserved for a genuinely post-barrier candidate** and is exercised by CASE 1
  in the post-barrier world, never by trade 25. **This is the arc's headline cost, and the test
  states it as the expected result rather than as a shortfall** -- see S2.7 and S8-L2b.
* **Migration:** applies to a v36 fixture; twice is a no-op; the CADL row survives as `'last_word'`;
  the backfill produces exactly one link row at `pre_barrier_reconstructed`; raw INSERTs of every
  incoherent tier/column combination are rejected (a raw INSERT never constructs the dataclass, so
  a `__post_init__`-only design would accept them -- the `0036` R7 M2 lesson); the minting trigger
  fires on a `record_intent` acceptance and does NOT fire on `place` / `decline` / `cancel` /
  `attest` / a non-accepted validity row.
* **No stored cap** (S2.1 property 3): a test asserts `latch_order_mandate_links` has no
  cap-shaped column, so the SQL-vs-Python arithmetic fork cannot be reintroduced by a later edit.
* **Envelope round-trip from the REAL emitter:** the fixture is built by calling
  `entry_auto_fill`'s writer, never hand-written.
* **Every admitting case carries its `-pre` twin** (S3 convention) -- the discriminator for RD's
  rung 9, and the one convention whose omission would let a whole ruling go unimplemented while the
  suite stays green.
* **Two spellings, one test.** Where a rule exists in both SQL and Python -- the freeze-tier
  comparison (S4.5C), the `_CLEAR_REASON_RANK` tie (S2.3.1a), the mandate limit (S2.4.1) -- a test
  runs BOTH spellings over the same fixtures and asserts they agree. This is the D6 class and a
  single-spelling test cannot see it.
* **Tests that pin a LIMITATION rather than a guarantee say so in their own docstring**: cases 31
  (criteria drift is VISIBLE, not refused), 33 (the low-id tier is CONSERVATIVE, not exact) and
  34a-34b (fabricated-but-coherent coverage arrays are ACCEPTED by the trigger). **Their green must
  never be read as proof of the property they sit next to**, which is exactly how a limitation
  becomes an assumed guarantee two arcs later.

---

## S7. TASK LADDER (TDD; one red -> green -> commit per task)

> ### THE ORDER IS TOPOLOGICAL, AND THE PREVIOUS ONE WAS NOT RUNNABLE (review 22A-R7-09)
>
> **Three tasks could not have satisfied their own acceptance at the point they ran:** task 1
> accepted case 15f, whose per-ticker cardinality is implemented in task 4; task 2 accepted cases
> requiring the link table and minting SQL from task 3; task 4 accepted competitor-liveness cases
> needing the reader parameters and `mandate_alive_at` from tasks 5-6. **Under the one-red-green-
> cycle-per-task rule that is not a documentation defect -- it would have stopped the executing
> implementer on day one**, and no review round had reached the ladder because every round was
> attacking the DESIGN.
>
> **The corrected order is FOUNDATIONS -> READER/ALIVENESS -> AUTHORIZATION -> COMPOSITION ->
> SURFACES**, and each task's acceptance is narrowed to what is implementable AT that stage. The
> rule applied throughout: **a task may only accept cases whose every dependency has already
> shipped in an earlier task.**

| # | task | touches | acceptance |
|---|---|---|---|
| 1 | Envelope key constant + reader + `AcceptedLatchOrder` + the **envelope-shape** guards only (origin, ticker, quantity, price) | `latched_origin.py` (new), `entry_auto_fill.py` (import) | cases **15a-15e**, 15d-i, 15d-ii, **and 30a-30d** (the price guard is one of the four shape guards this task ships, and its cases were implemented here and accepted nowhere -- review 22A-R8-08); real-emitter round-trip. **30a-30d are runnable here** because `assert_fill_consistent_with_order` is a PURE function over a hand-constructed `AcceptedLatchOrder` and needs no link table. **15f MOVED to task 4** -- its per-ticker cardinality is implemented there, and accepting it here was the clearest instance of 22A-R7-09 |
| 2 | **MIGRATION `0037`, COMPLETE AND IN ONE TASK -- THE WHOLE `.sql` FILE AND ITS SINGLE VERSION BUMP v36 -> v37 (review 22A-R9-11).** The `candidates` UPDATE+DELETE barrier + **`trg_candidates_no_replace`** (S4.5-replace) + the SINGLE-STATE epoch table with its THREE triggers, the `BEFORE INSERT` one created AFTER the seeding row (S4.5-epoch) + the link table with its append-only triggers + the guarded minting trigger (tier via the S4.5C `CASE`, never hard-coded) + the backfill + **the SIX `provenance_corrections` `ADD COLUMN`s and the two transactional trigger replacements** (S4.3) | `swing/data/migrations/0037_*.sql` ONLY | **SCHEMA-LEVEL tests, all runnable against the migrated fixture: cases 26, 33, 35a-35c, 35n, 35p, 36, 43, 44, 51a-51e**; the migration applies to a v36 fixture; **run twice is a no-op**; the CADL row survives as `'last_word'`; the backfill produces exactly ONE link row at `pre_barrier_reconstructed`; the junk-pivot no-raise test; **`ruff` and the pipeline `_step_evaluate` path still green**. **Every barrier/epoch case asserts `recursive_triggers` at its DEFAULT rather than setting it.** *(Cases 35d-35m assert ERA behaviour and leave with 22-A2.)* |
| 3 | **NO SCHEMA -- the Python side of what task 2 migrated:** models / repos / enums (`LatchOrderMandateLink`, the SIX `ProvenanceCorrection` fields, `PROVENANCE_ADMISSION_TIERS`, `LATCH_FREEZE_TIERS`), `swing/data/repos/latch_order_mandate_links.py`, and **`freeze_tier_for_candidate` -- THE one epoch reader, carrying the S2.4d.1 BODY-comparison barrier-integrity check against the pinned canonical DDL** (S4.5C) | `swing/data/models.py`, `swing/data/repos/` | **case 25** (minting behaviour, observed through the repo); **cases 50a-50e** (the integrity check, including **50d's same-name NO-OP trigger** and 50e's wrong-`tbl_name` / whitespace-only pair); the SQL-vs-Python freeze-tier drift test over SINGLE-STATE fixtures -- **the one instrument that does not depend on choosing the right grep (22A-R7-03)**; the enum drift test |
| 4 | `find_accepted_latch_order` (raw COUNT lookup) + **`authorize_accepted_order` carrying TEN of S2.4's ELEVEN rungs -- 1, 2, 3, 3b, 3c, 4, 5, 6, 7 and 9** (ticker; **link parent coherence**; **linked-validity outcome**; latest-child; **duplicated-field binding**; **governing place cycle**; **cancellation**; **order-linked consumption**; **its evidence-intact guard**; **rung 9 pre-barrier + the `sqlite_master` existence check**), plus cardinality by COUNT. **RUNG 8 IS NOT HERE -- it is task 6a's** | `latched_origin.py` | cases 4, 4c-i, 4c-ii, 4d(i), 4d(ii), 13, 14, **15f** (inherited from task 1), 22, 22b, 29a-29d, **41a** (rung 2's only case -- the function implements the rung here and no task accepted it: review 22A-R8-08), 47a-47c. **Cases 23, 23b-23d (competitor LIVENESS) MOVE to task 6a** -- liveness needs `mandate_alive_at` and the strict reader parameters from tasks 5-6, so accepting them here was 22A-R7-09's third instance. `-pre` twins ride with each case's own task |
| 5 | EXT-1 all THREE parameters (`criteria_lapse_armed_override`, `exclude_trade_ids`, `strict_decisions`) | `swing/latches/reader.py` | defaults preserve behaviour byte-for-byte on all three; strict-loader-failure and subject-present tests live in THIS task |
| 6 | `mandate_alive_at` (probe **selected by `candidate_set` membership**, `clear_reason`, **the UNIFORM same-session tie rule imported from the ladder**, coverage incl. interior gaps, **the snapshot cross-check -- THE ARC'S SINGLE ROUNDING AUTHORITY, S2.3.2/S4.3a**, session guard, decision as-of ordering, invariant error) | `latched_origin.py` | cases **5a, 5b**, 6, 7, 7b, 8, 9, 9b, 10, 11, 11b, 11c, 16, **19, 20** (decision evidence + as-of ordering -- read HERE), **24** (one archive read), **27, 28a-28c, 28d', 28e, 28f** (the tie rule's boundaries -- 28e/28f pin that it does NOT widen, and without them 28a-28c pass an over-wide rule), **41b-41e**. *(All ten additions were implemented by this task and accepted by no task -- review 22A-R8-08.)* |
| 6a | **Rung 8 -- competitor liveness (three-valued) -- SOLE OWNER**, which needs `mandate_alive_at` from task 6 to evaluate each competitor. *(Task 4's rung list previously named it too, so rung 8 was claimed twice and rung 2 and rung 3c not at all -- review 22A-R8-08.)* | `latched_origin.py` | cases 23, 23b-23d (inherited from task 4 per 22A-R7-09) |
| 7 | `derive_cohort_keys_for_fire` extraction | `cohort_provenance_correction.py` | Demand-C suite green UNCHANGED; CADL golden; rule-version pin re-derived |
| 8 | `resolve_latched_provenance` composition + the decline-reason closure test | `latched_origin.py` | cases 1-6 at the resolver level; case 18 |
| 9 | `record_entry` wiring + `cfg` kwarg + **`BEGIN IMMEDIATE` on every order-id-carrying request** + the three-way outcome + **the RELOCATED PE-anchor guard, evaluated INSIDE the transaction (S5.2-S5.5, review 22A-R9-03)** + WARNING logs | `entry.py`, `cli.py`, `web/routes/trades.py` (call site) | cases 1-6 end-to-end **plus their `-pre` twins**; the S2.2(a)-(d) LOCK matrix with `cfg` PASSED; cases 12, 21, 21b, **37c (the STABLE no-link PE-anchor refusal -- the case that fails an implementation which defers the route guard without relocating it)** |
| 10 | EXT-2 (tier-(e) + order-id shape rung) | `web/routes/trades.py` | **BOTH branches named:** an ADMITTED latched-with-PE-anchor entry passes through, **and a RECOGNISED-AND-REFUSED one also passes through** (case 37) -- an acceptance naming only the first passes an implementation that still rejects (c) |
| 11 | **NO SCHEMA -- task 2 already landed the columns and the trigger replacements.** The Demand-C dispatch (with the exclusion), the tier resolved before the last-word guard, and the CLI output | `cohort_provenance_correction.py`, `cli.py` | append-only closure (real updates, **all SIX** columns, three directions, driven off `PRAGMA table_info` rather than a re-typed list); probe-evidence cases with their **VERDICT MATRIX STATED, because FOUR of them are ACCEPTANCES (review 22A-R4-09, extended by 22A-R8-10): 34a ACCEPT, 34b ACCEPT** (the coverage-truthfulness LIMIT), **34f ACCEPT, 34g ACCEPT** (the single-rounding-authority LIMIT and its discriminator -- S4.3a; **and see inherited finding 22A-R9-05: 34g AS SPECIFIED DOES NOT DISCRIMINATE and must be re-fixtured before it is written**), **34c / 34d / 34e REJECT**, **39a / 39b / 39c REJECT**; the `$.authorization` block **48a-48p REJECT** + **49a-49i REJECT** + **49j ACCEPT**; **case 17** (the exclusion parameter, post-barrier synthetic) and **case 31** (the criteria-drift REVEALING test) |
| 11a | **Preserve fill identity through the replacement path** (S2.4a fix 1) | `trades/reconciliation_auto_correct.py` | case 22c -- split a Schwab-envelope fill; every partial keeps `fill_origin` + `schwab_source_value_json` |
| 12 | (EXT-3, separable) latch-aware form prefill | `web/view_models/trades.py` | prefill shows the fire's label |
| 13 | Full fast suite green; `ruff check swing/` clean | -- | counts read off the final head |

Tasks 1-4, 6, 8-9 are the stop-the-bleeding core. **TASK 11b IS DELETED, NOT DEFERRED-IN-PLACE
(Option C).** It was the tier-2 admission task -- the `--frozen-value-evidence` option, the
four-criterion preflight, the replay contract and **trade 25's correction** -- and all of it is
CARVED to 22-A2 (S12). *(It survived the first carve sweep as a fully-specified task in the ladder
an executor follows, which would have had someone building the carved machinery: the
survivors-by-inertia class, on the one surface where it is build-directing rather than narrative.)*
**The five-option CLI manifest pin therefore stays GREEN and is NOT updated by this arc.**
**Task 2 is load-bearing for the whole proof (S4.5) and is NOT droppable. It is UNBLOCKED**:
CHARC approved BOTH Condition-4 exceptions on 2026-08-24, including the epoch's THREE triggers
(S4.5B). *(This sentence previously said task 2 "DOES NOT START UNTIL CHARC RULES" and named the
obsolete TWO-trigger ask -- review 22A-R6-13. Stale blocking text can stop an executor on a
decision that has already been made, which is a different failure from being wrong.)* Tasks 5 and 10 are EXT-1 and EXT-2, both approved and both non-negotiable; task 12 is
EXT-3, approved as optional.

**ORDERING NOTE FOR THE EXECUTOR:** task 11a is small, independent of the migration, and fixes a
live data-loss path that exists whether or not this arc ships. **It is the only task in the ladder
with no dependency on the barrier**, so it is also the safe place to start.

> ### THE CASE-TO-TASK CLOSURE CHECK -- because THREE hand passes over this ladder each left holes (review 22A-R8-08)
>
> **22A-R7-09 re-ordered the ladder by hand and left three tasks accepting cases they could not
> run. My fix for it re-assigned cases by hand and left ELEVEN cases implemented by a task and
> accepted by none** -- 41a in task 4; 19, 20, 24, 28e, 28f and 41b-41e in task 6; 30a-30d in task
> 1 -- **while rung 8 was claimed by two tasks and rungs 2 and 3c by neither.** Three passes, three
> hole-sets. **The instrument cannot be another pass.**
>
> **THE CHECK, and it runs in Task 13 beside the suite and ruff:** a test collects **every case id
> named anywhere in S3 (the six cases and their sub-labels), S3.7's lens and S5.1's reason view**,
> collects **every case id named in an ACCEPTANCE cell of this ladder**, and asserts the two sets
> are EQUAL. A case in the plan and in no acceptance cell is an unowned test; a case in an
> acceptance cell and nowhere else is a phantom. **Both directions fail loudly, which is the half a
> one-directional check would miss** -- every hand pass above found only the direction it was
> looking for.
>
> **PREFER THE STATIC WALK.** The check reads the plan's tables, not a test-run trace: a trace only
> sees the cases a fixture happened to reach, which is exactly how eleven of them stayed invisible
> through two reviews and a self-sweep.
>
> **AND THE RUNG-TO-TASK DIRECTION IS THE SAME CHECK ON THE OTHER AXIS:** every one of S2.4's
> ELEVEN rungs appears in EXACTLY ONE acceptance cell's rung list. **Ten in task 4, rung 8 in task
> 6a, none twice, none missing.**

> ### ONE MIGRATION, ONE TASK -- NEVER STAGED ACROSS COMMITS (review 22A-R9-11)
>
> **The ladder previously split migration `0037` across THREE red->green->COMMIT tasks** (2: barrier
> + epoch; 3: link table + minting; 11: the `provenance_corrections` columns and trigger
> replacements), **while task 2 also tested migration idempotence.** That is unrunnable, and it
> fails SILENTLY rather than loudly.
>
> **The runner applies a migration ONCE, and only when its version is strictly greater than the
> database's current version** -- `current = _current_version(conn); if current >= target_version:
> return` (`swing/data/db.py:1965-1966`) and `if current < version <= apply_ceiling:` (`:2102`),
> **both read on disk.** So the moment task 2 commits and any development or copied database records
> **schema version 37**, every later edit to the SAME `0037` file **never runs on that database
> again.** Task 3's link table and task 11's columns would exist in the file and not in the
> developer's DB.
>
> **And CI would not catch it.** Fresh-fixture tests build from scratch and apply the whole file, so
> they stay green **while the executor's own database silently lacks two thirds of the schema** --
> the divergence then surfaces as inexplicable failures in unrelated tasks.
>
> **THE RULE, general rather than a patch to this ladder: a versioned migration file is an ATOMIC
> deliverable. It lands COMPLETE, in ONE task, with ONE version bump.** Task 2 is now that task.
> **The Python that READS the schema is freely splittable** -- which is what tasks 3 and 11 became
> -- **because reading is not versioned.**
>
> **This also dissolves an FK ordering problem the split had hidden:** `cited_latch_link_id
> REFERENCES latch_order_mandate_links(link_id)` (S4.3) could never have been added by task 11 to a
> table task 3 created, **as two separate applications** -- they must be in one file regardless,
> which is the same fact arriving from the other direction.

---

## S8. ACCEPTED LIMITATIONS, WITH THEIR REASONS

Repeated verbatim in every review prompt, with challenge invited.

* **L1 -- The invalidation branch has no LIVE case.** Covered only by synthetic cases 5, 6 and
  their variants. *Reason:* no live fill has ever met a breached mandate through a validated order.
  Labelled synthetic in the code.
* **L2 -- No structural proof exists for any fire created BEFORE migration 0037, which is every
  fire that exists today, including OII's 12284.** *Reason:* the `candidates` barrier cannot reach
  backwards and the acceptance snapshot did not exist then. **RULED BY RD 2026-08-24:**
  pre-barrier admission REFUSES BY DEFAULT (`pre_barrier_unproven`) -- **and under Option C that is
  the WHOLE of the ruling this arc encodes.** RD also created a TIER-2 class admitting on an
  immutable external contemporaneous record, **and that class is CARVED to 22-A2 (S12), AS RULED.**
  *(Its residuals travel with it: trade 25's evidence leaves a 2.38-day uncovered window, fire
  `2026-08-07T17:30:02` -> record `2026-08-10T02:41:33-10:00`, covered by writer-absence only, and
  it attests the PIVOT and STOP but not `candidate_criteria` -- L13.)*
  **THE LIMITATION AS IT STANDS IN THIS ARC IS SIMPLER AND LARGER: no pre-barrier fire is admitted
  by any path, so no correction of any existing trade is possible.** Trade 25 included -- see L2c.
* **L2c -- TRADE 25 IS NOT CORRECTED BY THIS ARC, and neither is any other existing trade.**
  *Reason:* the tier-2 evidence class that would have admitted it is CARVED to 22-A2 (Option C,
  ratified by both directors 2026-08-24), on the evidence that ten of thirteen recent CRITICALs
  lived in that machinery. **Consequence, costed rather than noted:** trade 25 keeps a pending-label
  row -- `manual_off_pipeline`, `candidate_id` NULL, `hypothesis_label` NULL (measured on the live
  row) -- **which governs every monthly read until 22-A2 lands.** RD's marker: tolerable for one
  read, increasingly costly after, and **22-A2 should land BEFORE THE OCTOBER READ if trade 25 has
  closed by then.** This is the arc's headline cost and it is stated as a limitation because it is
  one, not because the carve was wrong.
* **L2b -- On the day 0037 lands the ENTRY path admits nothing.** *Reason:* rung 9 plus the fact
  that every existing fire is pre-barrier. The mechanism becomes structurally live at the first
  post-migration A+ fire. **Stated because a green acceptance suite would otherwise imply a live
  mechanism**, and because the arc's stop-the-bleeding value is prospective by construction.
* **L3 -- Only Schwab-sourced fills can be admitted.** *Reason:* admission rests on broker-grade
  identity; case 4b shows a heuristic admission is indistinguishable from a real one.
* **L4 -- The derived label silently replaces a submitted one on the ADMITTED path (if EXT-3 is
  declined).** *Reason:* refusing a money-bearing entry over a cohort key inverts the priority
  `0036:26-38` establishes. Mitigated by a WARNING naming both values. (On the REFUSED path the
  label is written NULL and the submitted value is logged -- S2.2.)
* **L5 -- The probe rebuilds the whole latch derivation.** *Reason:* delegation beats a cheaper
  re-implementation, which is the divergence class. Runs only after an accepted link matches.
* **L6 -- The OHLCV parquet archive is a mutable input.** *Reason:* the shipped latch panel's
  existing exposure; the arc adds none, and the coverage gate converts absence OR incompleteness
  into a refusal rather than a survival.
* **L7 -- Trade 20 is NOT corrected by this arc.** Its vocabulary is 22-B's.
* **L8 -- No first-class entry-time provenance ledger, and the envelope scan that stands in for one
  is DESTRUCTIBLE.** *Reason:* `provenance_corrections` is for CORRECTIONS (unique per trade,
  pre-value pinned to the unset state); an entry-time ledger is new schema this arc was not
  commissioned to add. Consumption is therefore established by scanning other trades' entry-fill
  envelopes for this broker order id (review 22A-R15-07). **CORRECTED after review 22A-R3-02: my
  previous reason claimed that scan was authoritative for `schwab_auto` fills. It is not.** The
  supported split-into-partials handler rebuilds fills without `fill_origin` or
  `schwab_source_value_json` (`reconciliation_auto_correct.py:2988-3008`, read in full), so a
  consumption can VANISH from the representation the scan trusts. Task 11a stops the loss going
  forward; rung 7 refuses where a rebuilt row already lost it. **Live incidence: 26 of 51 fills
  carry an order-id envelope; none has been through the split handler yet** -- measured, and stated
  as service-prevention rather than schema-prevention, which is weaker.
* ~~**L15 -- Tier-2's TIME anchor is practical, not cryptographic**~~ **-- CARVED TO 22-A2 WITH
  THE TIER-2 CLASS (S12). It constrains nothing in this arc, which admits no pre-barrier fire at
  all.** The entry is kept struck, with RD's ruling intact below, **because the ruling is his and
  travels AS RULED -- and because a limitation silently deleted at a carve is indistinguishable
  from one silently dropped.** Everything from here to the end of this bullet is 22-A2's inheritance
  and binds nothing in 22-A:

  *Reason:* git author/committer dates are caller-settable and a local `main` is rewritable, so the
  service's checks establish content integrity and internal consistency, not that the record
  pre-dates the outcome. **RD ACCEPTED THIS 2026-08-24 and restated the class on its honest
  basis:**

  > Tier-2 snapshot evidence is strong **in proportion to what has been BUILT ON the commit and
  > where it has been REPLICATED.** The correction row records the basis **per case**:
  > ancestor-of-main, descendant depth, remote replication, and the uncovered window. **A shallow
  > or unpushed snapshot is correspondingly weak and may not qualify.**

  **RD REPLACED THE GRADED PHRASING WITH A BINARY CONJUNCTION on 2026-08-24 (review 22A-R6-07),
  and this entry survived the replacement unchanged until review 22A-R7-07 caught it.** It still
  said "GRADED standard", still said a short chain "may fail to qualify", and still specified
  refuse-on-any-divergence at replay -- **three claims S2.7 contradicts two sections away, and the
  third re-introduces exactly the behaviour RD rejected.** A direct survivor of a withdrawn rule,
  which is the class this loop has now met fourteen times.

  **The entry, restated correctly:** tier-2 admits **iff all FOUR** binary criteria hold (S2.7) --
  ancestor of `origin/main`; recorded date strictly before the fill session; recorded values
  matching the cited candidate at `PRICE_DP`; uncovered window computed and recorded.
  **`descendant_count` and `anchor_strength` are ATTESTATIONS ONLY and are NEVER verdict-bearing**,
  so a short chain does not disqualify anything by itself. **Replay re-evaluates the four; it
  refuses only when a CRITERION fails, never when a non-verdict attestation moves** -- descendant
  counts GROW in a healthy repo, and treating growth as staleness would refuse every re-derivation
  forever.

  **The residual that is genuinely a limitation, and all this entry should ever have claimed:** the
  four criteria establish content integrity, replication and internal consistency. **They do not
  establish an independent TIME anchor** -- git author/committer dates are caller-settable and a
  local `main` is rewritable -- so criterion 1 (`origin/main` ancestry) is doing the tamper-anchor
  work, and it is a practical anchor rather than a cryptographic one. Trade 25 satisfies all four
  (S1.5.4).

* **L16 -- SQL CANNOT VERIFY THAT THE RECORDED PRICE-COMPARISON VERDICT IS THE CORRECT ROUNDING OF
  ITS OPERANDS** (S4.3a, review 22A-R8-10). *Reason:* the arc enforces a SINGLE ROUNDING AUTHORITY
  -- the service compares at `PRICE_DP`, SQL binds raw operands by identity and stores the verdict
  as a datum. **Any SQL-side recomputation re-creates the cross-domain comparison the rule exists to
  forbid**, because Python rounds half-to-even and SQLite rounds half-away-from-zero, and they
  disagree on 24 measured live `candidates` rows. Consequence: a raw INSERT could cite two
  genuinely-correct raw values and fabricate the verdict over them. **Strictly smaller than the
  exposure it replaced** -- the raws stay bound to the cited link and candidate, so no forgery can
  name a different mandate. Case 34f pins the limit; case 34g pins the rule.
* **L17 (AL-3) -- SOME CITATION-TRIGGER CLAUSES ARE SERVICE-VALIDATED: SQL asserts presence, type
  and verdict, and the judgment rests on state no subquery can reach. A FABRICATED value is
  ACCEPTED on every member below.** *Reason, per member, is stated with the member -- a roster
  whose entries share one borrowed reason is how `22A-R9-05` happened.*

  **THE ROSTER BELOW IS CLOSURE-CHECKED, NOT HAND-MAINTAINED** (operator-ruled 2026-08-27).
  `tests/data/test_22a_al3_closure.py` holds it against what the CODE classifies
  (`AUTHORIZATION_CLAUSES` + `PROBE_GUARD_CLAUSES`, the `binding` field) and against what the
  MIGRATION actually binds, **in both directions**: a clause added later as service-validated with
  no entry here FAILS, an entry claiming a clause the code SQL-binds FAILS, an entry whose declared
  AXIS disagrees with the migration FAILS, and an entry with no executing PIN FAILS. *This roster
  said "exactly those three" through eleven dispatches while the code classified FIVE; the check
  named the two missing members on its first run. It has been wrong three times in both
  directions -- `22A-R9-05` broadened it, `SS-12` was the same shape one member short on the
  barrier roster, `22A-R12-02`/`22A-R12-03` found it short by two -- and* **the roster is not the
  fix; the closure check is.**

  **THE AXIS IS PART OF THE DECLARATION, because a two-valued SQL_BOUND/SERVICE_VALIDATED label
  cannot say WHICH half is unproved** -- and that ambiguity is exactly how a clause whose INPUT is
  bound and whose VERDICT is not stayed unnamed. `INPUT_UNBOUND`: the migration binds nothing, so
  any value passes. `VERDICT_UNPROVEN`: the input IS bound to its source and the predicate over it
  is not proved. `PREDICATE_WEAKER_THAN_THE_SERVICE`: a citation-graph clause outside the probe
  blob whose SQL predicate admits strictly more than the service's. `SET_INCOMPLETE`: every
  supplied element is bound and the COMPLETENESS of the supply is not.

<!-- AL3-ROSTER-BEGIN -->
  * `rung7_consumption_scan_fill_ids` -- INPUT_UNBOUND -- the consumption scan's RESULT; no
    subquery can reach it. PIN: `tests/data/test_22a_task11_citation_evidence.py::test_a_fabricated_input_on_a_service_validated_rung_is_accepted_case_49j`
  * `rung8_competitor_link_ids` -- INPUT_UNBOUND -- derivation state; no subquery can walk the
    fold. PIN: `tests/data/test_22a_task11_citation_evidence.py::test_a_fabricated_input_on_a_service_validated_rung_is_accepted_case_49j`
  * `fire_membership` -- INPUT_UNBOUND -- the COUNT of latches whose `candidate_set` contains the
    fire is fold state, so SQL binds the input to the literal 1 and cannot check that the count IS
    one. The pin builds a world carrying TWO accepted orders on the candidate -- the state the
    service refuses as `ambiguous_accepted_orders` -- and the citation still inserts.
    PIN: `tests/data/test_22a_task11_citation_evidence.py::test_THE_DECLARED_LIMITATION_a_fabricated_fire_membership_is_ACCEPTED`
  * `fill_session_is_session` -- VERDICT_UNPROVEN -- the input IS bound to
    `entry_fill_session_date`, and no trigger can enumerate an exchange-session calendar, so a
    fabricated weekend or holiday session asserting `pass` is admitted. Same ground as AL-5 one
    clause over. *Reclassified in the code at `22A-R6-06` and named here only at `22A-R12-03`: the
    code was truthful and this declaration was not.*
    PIN: `tests/data/test_22a_task11_citation_evidence.py::test_a_weekend_fill_session_is_ACCEPTED_and_the_limit_is_declared`
  * `anchoring_fill_is_authoritative` -- PREDICATE_WEAKER_THAN_THE_SERVICE -- the citation-graph
    clause proves `entry_fill_id_at_correction` is AN entry fill of this trade on the frozen
    session; the service means THE FIRST by (parsed `fill_datetime`, `fill_id`) after refusing any
    malformed sibling (`resolve_authoritative_entry_fill`). A later scale-in fill can therefore
    anchor a citation the service would never build. *Inherited VERBATIM from 0036 and not
    introduced here.* **There is no SQL fix by construction:** the ordering is a Python parse over
    an unconstrained TEXT column -- the repo's lexical `ORDER BY` mis-ranks a schema-legal
    basic-form timestamp, which is why the service does not reuse it -- so re-deriving it in SQL is
    the engine-boundary violation the persist-canonical ruling forbids, and persisting the judgment
    does not help because the column IS the persisted judgment and a raw writer forges it with its
    citation (L18's shape). *V2 fix: a constrained timestamp column, which is a migration beyond
    this arc.* ANCHOR: `-- the anchoring fill is an ENTRY fill of THIS trade on the frozen session`
    PIN: `tests/data/test_22a_task11_citation_evidence.py::test_THE_DECLARED_LIMITATION_a_non_authoritative_anchor_is_ACCEPTED`
<!-- AL3-ROSTER-END -->

  **REASONED EXCLUSION -- service-validated in the code roster and DELIBERATELY NOT AL-3.** Listed
  rather than omitted, because an unstated boundary is the hand-enumerated-roster failure again:

<!-- AL3-EXCLUSIONS-BEGIN -->
  * `decision_ordering` -- SET_INCOMPLETE -- every pair the writer SUPPLIED is bound by subquery to
    a real `latch_order_intents` row on BOTH halves, which is strictly MORE than any AL-3 member
    gets; what is unproved is the COMPLETENESS of the supply, and an EMPTY array satisfies the
    clause vacuously. *CHARC ruled 2026-08-26 (`22A-R9-05`) that AL-3 does NOT extend here and that
    this clause carries its own declaration, which is AL-3b. Banked to 22-A2 with its trigger.*
    PIN: `tests/data/test_22a_task11_citation_evidence.py::test_an_EMPTY_decision_ordering_array_is_accepted_the_declared_limit`
<!-- AL3-EXCLUSIONS-END -->
* **L14 -- Consumption has no durable record; it is INFERRED from surviving evidence.** *Reason:*
  the durable order-to-trade table is new schema beyond this arc. Consequence: the mechanism can
  refuse where it cannot prove non-consumption (fail-closed), and after Task 11a it cannot silently
  admit twice. **V2: the consumption table. S10-F7.**
* **L13 -- `candidate_criteria` is NOT frozen, so the label's failed-criteria SUFFIX is not
  provably contemporaneous** (S2.6.5, review 22A-R3-09). *Reason:* freezing it is two more triggers
  on a third table, beyond CHARC's CONDITION 4, and the suffix is cohort bookkeeping rather than
  the money-bearing comparison -- so the plan narrows the claim. **And the mitigation is
  narrower still than my previous draft said (review 22A-R4-04): the criteria basis is persisted
  only on the CORRECTION path, in `cited_latch_probe_json`. On the ENTRY path nothing durable
  records it** -- `probe_evidence` is in-memory, and a WARNING log is not a record -- **so on the
  entry path there is no detection, only prevention's absence.** Detection is strictly weaker than
  prevention; no detection is weaker again, and this entry says so rather than letting "recorded at
  admission" cover both paths.

  **CHARC RULED ON THIS 2026-08-24: L13 STANDS -- the judgment is UPHELD, not overruled -- and his
  reasoning is recorded because it marks where the boundary is.** Cohort membership is decided by
  `label_matches_hypothesis` (`swing/metrics/label_match.py:26-37`, **read in full and VERIFIED
  here**: it matches on exact equality, on `name + " "`, or on `name + ";"`), **so a label matches
  its hypothesis with or without the failed-criteria suffix.** Criteria drift can therefore change
  the SUFFIX but **cannot move a trade between cohorts**; it can only make a re-derivation's suffix
  disagree with the stored label, and Demand C's drift reader is already the instrument that
  surfaces exactly that. Extending the barrier to a second table on a cosmetic-drift consequence
  would be scope creep past the evidence. **REVISIT TRIGGER, stated so this is a decision with an
  expiry rather than a permanent shrug: if the drift reader ever fires on a criteria-suffix
  mismatch in PRODUCTION, L13 re-opens and the barrier is re-proposed.**

  **Trade 25 is affected**: its derived label `'A+ baseline (aplus)'` has no suffix, and a criteria
  deletion would produce the same empty suffix, so the absence is not self-proving -- **but under
  the ruling above that is a suffix-fidelity question, not a cohort-membership one**, which is
  precisely the bound CHARC drew.
* **L9 -- The `fill` terminal is heuristic evidence** (S2.3.1). *Reason:* `_match_fill`'s windowed
  rung does not inspect order ids. Mitigated: consumption is established by the order-id envelope
  scan above, and a `fill`-driven refusal names the trade and its `fill_link_basis`. The residual
  is a possible FALSE REFUSAL -- fail-closed, never a false admission.
* **L11 -- Decisions are time-scoped conservatively and coarsely** (S2.3.4b). *Reason:*
  `recorded_ts` is naive LOCAL and a fill carries only a DATE, so the as-of comparison is
  date-to-date in one domain and refuses same-session ambiguity outright rather than inventing a
  third clock domain to order them. It can only refuse, never admit.
* **L12 -- A future `candidates` pruner becomes a migration-level operation** (S4.5). *Reason:* the
  DELETE barrier is what makes the epoch's id comparison sound; relaxing it silently unsounds the
  freeze tier. Pruning is still possible -- drop trigger, prune, recreate, re-stamp the epoch -- it
  is simply no longer an ordinary write.
* **L10 -- The fill envelope is operator-submitted and its order id is not authenticated**
  (S2.4.1). *Reason:* `record_entry` cannot re-verify with the broker, and `fill_origin` is derived
  from the same hidden inputs, so no rung of the ladder is independent evidence. Threat model:
  single-operator local application; the realistic failure is a stale or mis-copied envelope, which
  every guard must simultaneously fail to catch. **What still gets through is named in S2.4.1.**
  V2 fix: a server-side nonce or a POST-time re-fetch. **Flagged for CHARC/RD.**
* **L18 -- THE CITATION TRIGGER CAN NO LONGER JUDGE A FILL'S ENVELOPE AT ALL; IT VERIFIES ONLY
  THAT THE AUTHORITY'S STORED READING AND THE CITATION AGREE. A RAW WRITER STORING TWO
  EQUAL-BUT-WRONG VALUES PASSES THE EQUALITY CHECK.** *(Declared at the PERSIST-CANONICAL reshape,
  CHARC + RD 2026-08-26, as a condition of the ruling -- stated NOW rather than discovered later.)*

  *Reason:* ten review rounds never converged, and three CONSECUTIVE rounds each produced a
  DISTINCT engine-semantic divergence between Python and SQLite -- `json.loads` ACCEPTS a document
  containing `NaN` where `json_valid` REJECTS it; `str.strip()` removes tab/newline/NBSP where
  `trim()` removes ASCII space only; `1002937461 == '1002937461'` is False in Python and True in
  SQL against a TEXT-affinity column. All three reproduced independently. Zero findings were ever
  reopened across 74, so this was never careless execution: it is a structural property of
  mirroring a nontrivial predicate across engines that disagree in at least three independent ways,
  and nothing said three was the last. **RD's sentence, adopted verbatim by CHARC into the
  convention: SQL VERIFIES A FACT; IT MUST NEVER RE-DERIVE A JUDGMENT ACROSS AN ENGINE BOUNDARY --
  the twin mirrors the AUTHORITY by consuming its OUTPUT, not by reimplementing its reasoning.**

  **WHAT WAS LOST, EXACTLY.** The trigger previously re-derived, in SQL, whether the subject fill's
  envelope was canonical (duplicate root keys, value type, padding, blankness) and what order id it
  named. It can no longer detect ANY of that. What it detects instead is DISAGREEMENT between two
  stored places: `fill_envelope_identity` (the authority's reading, bound to the exact document by
  `envelope_raw`) and the correction row's citation columns.

  **AND THIS IS THE SAME TRUST BOUNDARY AS BEFORE, which is why the loss is acceptable rather than
  merely accepted.** The old clause could equally be satisfied by a FORGED ENVELOPE: a raw writer
  who wrote a clean, canonical envelope naming an order it never came from passed every one of
  those checks. **The trigger never could judge truth -- only CONSISTENCY.** What changed is which
  two artefacts must agree, not whether truth was ever verifiable in SQL.

  **What it still catches, and these are not small:** a citation naming a different order than the
  stored reading; a reading the authority REFUSED; a document the authority has NOT read (the raw
  writer's own shape); and a document that CHANGED after its reading was taken -- the join is on
  the fill AND the document, so a substituted envelope stops matching and the surface fails CLOSED.

  **Pinned, not merely written down:** `tests/data/test_22a_task11_citation_evidence.py::
  test_THE_DECLARED_LIMITATION_two_equal_but_wrong_values_are_ACCEPTED` asserts the acceptance. If a
  later change makes that row REJECT, the limitation is narrower than declared and **the
  declaration must be corrected, not the test silenced.**

  *V2 fix:* none available in SQL, by construction. The only instrument that could close it is an
  authenticated envelope (L10's server-side nonce or POST-time re-fetch), which would make the
  document itself trustworthy and is the same fix L10 already names.

* **L19 (AL-11) -- NO CONSUMER OF A STORED READING CHECKS THE CANONICALISER VERSION IT WAS WRITTEN
  UNDER, IN SQL OR IN PYTHON.** *(Codex `22A-R13-02`, round 13. `canonicalizer_version` appeared
  EXACTLY ONCE in the shipped migration -- its column declaration -- while SEVEN trigger sites
  referenced the table; the round-12 clause that prompted this became the seventh by copying its
  neighbour's shape including its omission.)*

  *Reason:* the SERVICE is strictly stronger and cannot be mirrored here. `ensure_entry_fill_identities`
  re-runs the CURRENT canonicaliser over the whole population before any scan and `record_identity`
  RAISES when a stored answer disagrees with today's; SQL cannot re-run anything, and re-deriving
  the reading in SQL is the engine-boundary violation L18 forbids. **What is exposed:** after a
  canonicaliser bump whose ANSWER changes for some document, a RAW correction can be accepted on the
  older reading the service would refuse. **Direction: WRONG ACCEPTANCE, raw path only.**

  **THE OBVIOUS FIX -- "require the current version in every consumer" -- WAS MEASURED AND
  REJECTED, in both of its halves, and that is why this is a declaration rather than a patch:**
  1. **At TWO of the six it INVERTS.** `last_word_subject_order_id` and `rung6_consumption_scan`
     read a stored reading as EVIDENCE OF ABSENCE. Filtering them on the version makes a stale
     reading INVISIBLE, which WIDENS acceptance. A blanket sweep of "all seven" would have shipped
     exactly that -- the reason the treatment is a per-site READ and not a global edit.
  2. **At the other four it manufactures a REFUSAL ON THE SERVICE PATH.** An AGREEING older reading
     is deliberately left in place (`test_an_agreeing_older_reading_is_left_alone` -- filtering on
     the version LABEL would fail every historical reading on the day the constant moves). The
     service would authorize and the trigger would then ABORT: authorize-then-abort, met four times
     on this arc already.

  **SO THE ARMING ACTION IS GUARDED INSTEAD -- BY A LABEL COMPARATOR, AND THAT IS WHAT IT IS CALLED
  (amended 22A-R14-01, operator-ruled 2026-08-31).** A reading can only be stale if
  `ENVELOPE_CANONICALIZER_VERSION` MOVED between two writes; a row bearing a version nobody shipped
  is a forged identity row, which is L10/AL-10's class. `0037` therefore carries a
  `CANONICALIZER-VERSION-ANCHOR` mirroring the Python constant, and
  `tests/data/test_22a_canonicalizer_version_closure.py` compares the two representations -- so a
  LABEL bump FAILS THE SUITE, naming the required work, before any stale row can exist.

  **WHAT IT DOES NOT DO, AND THE COUNTEREXAMPLE IS THIS ARC'S OWN.** It compares a Python constant
  to a SQL COMMENT: **two hand-maintained copies of a LABEL, neither of which is the canonicaliser's
  BEHAVIOUR. A canonicaliser change without a version bump is INVISIBLE to it.** `22A-R13-01` made
  `canonical_envelope_identity` answer `refused` where it answered `canonical` for every non-`str`
  document; the constant did not move; and this tripwire -- shipped in the very next commit --
  passed. For six commits the paragraph above was FALSE while it still read TRUE. **This section
  previously said the exposure was "CLOSED"; it is not, and the earlier sentence was the same false
  claim this arc exists to remove**, which is why the wording is amended rather than the instrument
  widened: *the principle was never "make every instrument exact"; it is "do not claim exact when
  you are not."* The blindness is now PINNED, executed rather than described
  (`test_DECLARED_a_behaviour_change_WITHOUT_a_bump_is_invisible` restores the retired predicate,
  measures the moved answer, and calls the tripwire, which is green). A comparator over the
  canonicaliser's ANSWERS is **routed to 22-A2 (S12.2b)** with R14-01 as its founding evidence.
  *(Gotcha #11's rule applied and then read carefully: the only mirror that defends a set is the
  comparator -- but only over the representation it actually compares.)*

  **THE 2026-08-31.1 BUMP, AND WHY IT OWED NOTHING.** `R13-01` moved the answer, so the constant had
  to move with it. A bump normally owes re-attestation of readings taken under the older grammar;
  `0037` **creates `fill_envelope_identity` and inserts NOTHING into it** (asserted by
  `test_the_migration_SHIPS_THE_TABLE_EMPTY`, with a splice discriminator on the real file), and the
  migration is unapplied, so **no reading exists under either grammar on any database.** Once 0037
  is applied and the first reading is written, **that carve-out is SPENT** and the next bump owes
  the full re-attestation.

  **THE ROSTER BELOW IS CLOSURE-CHECKED, NOT HAND-MAINTAINED.** Every `FROM`/`JOIN` reference to
  `fill_envelope_identity` in `0037` carries an inline `-- FEI-CONSUMER <key> :: <claim>` marker;
  the test walks the migration, asserts markers and references INTERLEAVE one-for-one, asserts each
  marker's CLAIM against what its span actually contains, and holds the whole marker set against
  this roster **in both directions** -- a consumer added later without an entry FAILS, an entry
  naming no marker FAILS, and a clause that GAINS a version check while still declared blind FAILS.

<!-- AL11-ROSTER-BEGIN -->
  * `barrier_no_replace_conflict_scope` -- NOT_A_READING -- the append-only conflict scope addresses
    the UNIQUE KEY, never a reading. A version filter here would admit a SECOND row for the same
    document under a different version, defeating the append-only guarantee. **This one must stay
    version-blind even after 22-A2's re-attestation.**
  * `subject_reading_is_canonical` -- VERSION_BLIND -- the subject fill's reading exists and is not
    a refusal; a stale reading satisfies it.
  * `last_word_subject_order_id` -- VERSION_BLIND -- **evidence of ABSENCE**; filtering WIDENS.
  * `cited_order_is_the_subject_order` -- VERSION_BLIND -- the citation's order equals the stored
    reading's order, whatever grammar produced it.
  * `rung6_population_has_been_read` -- VERSION_BLIND -- population completeness; a stale reading
    counts as read.
  * `rung6_consumption_scan` -- VERSION_BLIND -- **evidence of ABSENCE**; filtering WIDENS.
  * `guard_envelope_symbol_binding` -- VERSION_BLIND -- the probe's symbol equals the stored
    reading's symbol.
<!-- AL11-ROSTER-END -->

  **THE PYTHON HALF IS THE SAME LIMITATION AND IS NOT OMITTED** (a boundary stated is a boundary
  that cannot be assumed away): `stored_identity`, `consuming_entry_fills` and
  `unreadable_entry_fills` in `swing/data/repos/fill_envelope_identity.py` are version-blind too.
  They are SAFE where the SQL is not, because every ladder caller runs
  `ensure_entry_fill_identities` first, which re-verifies the population and raises on disagreement
  -- and the test asserts they carry no version filter, so ADDING one would fail here and force this
  declaration to be corrected rather than silently narrowed.

  **PINNED IN BOTH ARMS, not merely written down (amended 22A-R14-06).** The single pin this
  section used to cite moved only the version LABEL, so the stored answer AGREED with today's: it
  measured the BENIGN acceptance, not the dangerous stale-ANSWER acceptance this limitation
  describes -- *a fix that rejected disagreeing readings while continuing to accept agreeing old
  labels would have closed the material exposure without making it fail.* Both arms now exist in
  `tests/data/test_22a_task11_citation_evidence.py`:
  `test_THE_DECLARED_LIMITATION_a_stale_AGREEING_LABEL_is_ACCEPTED` (benign, and deliberately
  preserved) and **`test_THE_DECLARED_LIMITATION_a_stale_DISAGREEING_reading_is_ACCEPTED`**, which
  restores the retired pre-`R13-01` predicate, has the PRODUCTION writer store `('canonical', NULL)`
  for a document today's authority reads `refused`, and shows the trigger ACCEPT. Its contrast is
  `test_a_BLOB_document_naming_an_accepted_order_cannot_claim_last_word` -- **same document, same
  payload, CURRENT reading, REJECTED.** *V2 fix, CARVED TO 22-A2 (S12.4):* an APPEND-ONLY
  RE-ATTESTATION design --
  `UNIQUE(fill_id, envelope_raw, canonicalizer_version)`, a writer that APPENDS a current-grammar
  reading instead of leaving an older one, and version-addressed consumers. That is a schema
  redesign of a table this arc introduces, and it is the only thing that closes the class without
  inverting two clauses or manufacturing a refusal.

---

## S9. THE OPERATOR GATE (post-merge, one step at a time)

0. **A FULL LIVE PIPELINE RUN, PRE-MERGE (CHARC CONDITION 1 -- BINDING, not a recommendation).**
   Backup, migrate a COPY of the live DB to v37, point a full `swing pipeline run` at it, and
   witness every step complete. **What it is for:** the barrier's residual risk is AVAILABILITY --
   an UPDATE or DELETE on `candidates` from a writer no grep saw would now `RAISE(ABORT)` and take
   the nightly down. *The nightly is the only instrument that converts "no writer visible" into
   "no writer on the paths the nightly exercises."* **A `RAISE(ABORT)` from either trigger is a
   STOP: the arc returns to CHARC, and the trigger is NOT relaxed to make the run pass.** This gate
   blocks the merge; it is not a post-merge smoke test.
1. Backup + `swing db migrate` to v37; witness the version, the backup gate, and that the backfill
   produced exactly ONE link row for OII at `pre_barrier_reconstructed`.
2. **Witness REFUSE-BY-DEFAULT on the live DB**, which under Option C is the arc's terminal
   behaviour for every existing trade rather than a step on the way to a correction:
   `swing journal correct-cohort-provenance 25 --cited-candidate 12284 --cited-recommendation 169
   --dry-run` -> witness the refusal **`pre_barrier_unproven`**, naming the freeze tier.
   **No correction is applied by this arc.** Trade 25 keeps its pending-label row until 22-A2.
3. **Witness the BARRIER-EXISTENCE CHECK (CHARC, 2026-08-24)** on a COPY: drop
   `trg_candidates_no_update`, re-run the dry-run, and witness **`barrier_not_installed`** rather
   than an admission. Restore the copy. **This is the step that proves single-state means
   armed-and-verifiably-armed-NOW.**
4. Witness that a POST-barrier fire would admit, using a synthetic candidate above the epoch
   boundary on the copy -- **the only structural admission this arc can demonstrate before a real
   post-migration A+ fire exists.**
5. **Witness the UNSEEDED default:** `--dry-run` on trade 24 (RHI) still refuses at the LAST-WORD
   guard with its existing message -- proving the unlatched path is untouched on the live DB, not
   only in fixtures.
6. Browser gate (EXT-2 ships, so this is not conditional): render the entry form for a ticker with
   an accepted latch order; witness the submit path end to end. EXT-3's prefill only if it ships.

**Calendar (brief S6):** RD's monthly read #3 runs the first trading week of September. This arc
lands BEFORE it or AFTER it, never across it.

---

## S10. FLAGGED, NOT FIXED

* **F1 -- `hypothesis_prefill.lookup_active_recommendation_label` is a THIRD consumer of the
  defective root.** `swing/recommendations/hypothesis_prefill.py:44` calls
  `latest_evaluation_run_id(conn)`, so the entry form prefills a label from the latest run rather
  than the mandate. Same family as S1.1. EXT-3 would fix it for the latched case only. Recommended
  as a named 22-D/22-G item.
* **F2 -- `_match_fill` can never match a trade whose `candidate_id` points at a NON-fire
  candidate.** The exact rung needs `candidate_id in cset`; the windowed rung needs
  `candidate_id IS NULL`. Trade 24 satisfies neither (`12518` vs cset `{12442}`), so RHI's real fill
  is invisible to its own latch and the mandate reads `armed` today, days after it filled. Live,
  current, outside scope. This arc's `candidate_id` write puts NEW latched fills on the exact rung
  but does nothing for this shape.
* **F3 -- `schwab_order_id` has five-plus read sites and no single source**
  (`swing/web/view_models/trades.py:988-1100`, `swing/trades/exit_auto_fill.py:535-600`,
  `swing/trades/entry_date_correction.py:758-790` and `:1263`, plus this arc). Task 1 adds the
  shared KEY constant; consolidating the READERS is a Tier-3 sweep.
* **F4 -- The hidden envelope's `schwab_order_id` is unvalidated at the route** unless EXT-2(b)
  ships (S2.4.1). The service-side ladder compensates; the route rung is defence in depth.
* **F5 -- `swing/latches/identity.py:11` asserts an immutability nothing enforces.** Task 2's barrier
  makes it true; the comment should be narrowed to what the code guarantees either way (#31).
* **F6 -- No entry-time provenance audit table** (S8-L8).
* **F7 -- No durable order-to-trade CONSUMPTION record** (S8-L14). Task 11a stops the evidence loss
  going forward; it does not reconstruct a consumption already erased by a completed split. The V2
  shape is a small append-only `order_consumptions` table written at admission. Recommended as a
  named 22-B/22-C item.
* **F9 -- ANY future check that reaches outside the process belongs in the PREFLIGHT phase**
  (S2.7, review 22A-R6-10). The correction service's `BEGIN IMMEDIATE` is a write reservation over
  the whole database, so a broker re-fetch, an HTTP call or a second-repo read placed inside it
  would block every writer including the nightly. **This arc contains no such check** -- the tier-2
  git fetch that motivated the rule is CARVED to 22-A2 (S12) -- **so F9 is recorded here as a
  STANDING RULE for the next arc that adds one, not as a live exposure in 22-A.** The distinction
  matters: a flagged item with no instance reads as an open risk when it is a preserved lesson.
* **F8 -- `candidate_criteria` is mutable and feeds a persisted label** (S8-L13, review 22A-R3-09).
  Two triggers would close it. Named at S4.5B so CHARC sees the surface; NOT requested by this
  plan, and if he disagrees with that judgment it is a one-task addition to Task 2.

---

## S11. REVIEW PLAN

Tier **`strong`** -- escalated from the writing-plans default by the orchestrator, on the ground
that this phase has just falsified the assumption behind that default: the acceptance gate was
itself the defect, authored by the director who owns the gate, and it would have passed both the
executing review and his own gate because every live case returned the same answer with or without
the clause. This plan's spine is that same gate.

Per-round mechanical assertions, all five: the banner model matches whatever `strong` resolves to
on THIS box (recorded, never assumed), `model_reasoning_effort` reads `high`, anchored `^ERROR`
count is zero, the anchored `^tokens used` footer is present, and exactly one anchored verdict
token appears. Plus a non-empty redirect target and a grep proving the round did not reach for
prior-round findings. Cumulative ledger in `.copowers-findings.md`, including the VOIDED pre-ruling
round, the DISQUALIFIED round 2a **and the harvest of its content** (a disqualified round counts
toward nothing and its findings are still adjudicated -- the gate is on ENDING the loop, not on
using the content); ledger check-in to the orchestrator at round 5 and every 5 after.

**A SIXTH MECHANICAL CHECK, added from this arc's own QA and now in the recipe
(`implementer-dispatch-recipe.md` S3, the 2026-08-24 entry):** before asserting an ABSENT footer,
confirm the codex process has demonstrably EXITED. Round 2a was disqualified on a missing footer
and re-run; at the orchestrator's QA the file was COMPLETE -- the process had kept running and
finished after the author read it. **A file that currently ends well can be mid-write, and a round
disqualified while still running wastes a sound round.** The conservative disqualification cost
only tokens and the content was harvested later; the failure mode worth avoiding is the opposite
one -- reading a transcript that is still being written.

Convergence criterion for a plan/doc: **result-bearing** findings only -- a finding that would
change a number, a verdict, a claim's scope, or the evidence under one. Two consecutive rounds with
zero result-bearing findings converge; contested classification counts as result-bearing. The
declared envelope (S0.1) and the accepted limitations (S8) go into every prompt verbatim with
challenge invited.

**Routing, updated for what is now RULED and what is now OPEN.**

**RULED and encoded, no longer routed:** S0.1's three extensions (CHARC, all approved; EXT-2 never
optional) * S4.5's barrier, UPDATE and DELETE (CHARC, with four binding conditions at S4.5A) *
S1.5.3 / S8-L2, whether a pre-barrier fire can be corrected (RD: refuse by default **-- which is
the whole of what 22-A encodes, the tier-2 half having been carved**).

**NOTHING IS OPEN. All four held items were ruled 2026-08-24; TWO are encoded here and TWO travel
to 22-A2 with the machinery they govern:**

1. **22A-R6-02 (CHARC) -- APPROVED and WIDENED, and it TRAVELS.** Continuity from the FIRE SESSION
   to the READ, any gap DEMOTING to tier-2, and the retirement-window twin all belong to the
   `[fire_session, read]` interval, which is CARVED (S12). **What is encoded HERE is the half that
   survives on its own: the epoch reader stays the ONE reader** (S4.5C), now also the sole owner of
   the `sqlite_master` existence check.
2. **22A-R6-06 (CHARC) -- MOOT BY DISSOLUTION.** EXT-4 withdrawn with the carve-out; the envelope is
   the three approved extensions (S0.1, S2.3.1c).
3. **22A-R6-04 (RD) -- ATTESTATION. TRAVELS to 22-A2** with `descendant_count` / `anchor_strength`
   (S12), preserved AS RULED.
4. **22A-R6-07 / 22A-R6-08 (RD) -- THE BINARY CONJUNCTION OF FOUR and the replay contract. TRAVEL
   to 22-A2** (S12), preserved AS RULED. *(Items 1, 3 and 4 previously read as "encoded" here, which
   was true before the carve and false after -- a routing ledger that still claims to have absorbed
   a ruling it has since deferred is the worst kind of stale, because it is exactly what a director
   re-reads at his gate.)*

**Both gates are now the destination rather than a dependency:** CHARC's section-3 gate (schema +
carve) and **RD's six-case gate -- 5a real-AMN REFUSE, 5b synthetic same-session ADMIT (with its
newly-written `5b-pre` twin), and 6 equality ADMIT.** *(The retirement-window pair 35g/35h was part
of this gate before the carve and tests ERA behaviour; it travels to 22-A2.)*

**NOTHING IS ROUTED AND NOTHING IS BLOCKED.** The CRITICAL that was with CHARC (22A-R7-02, the
`epoch_id` insert-order hole) **RESOLVED BY DISSOLUTION** under Option C -- single-state models no
era sequence for it to attack -- and it travels to 22-A2 with its evidence intact (S12.2).

> **ONE ITEM IS SURFACED FOR CHARC'S SECTION-3 GATE, and it is a change of SUBSTANCE at an
> UNCHANGED COUNT.** He approved **THREE** `CREATE TRIGGER`s on the epoch table as CONDITION-4
> EXCEPTION 1, where the third guarded an ERA SEQUENCE. **Single-state cannot represent an era
> sequence, so that third trigger travels -- and a DIFFERENT third trigger is required in its
> place**: a `BEFORE INSERT` barrier closing an `INSERT OR REPLACE` rewrite of the epoch row that is
> **measured OPEN at SQLite's default `recursive_triggers=OFF`, which this repo never enables**
> (S4.5-epoch; verified by execution on sqlite 3.50.4, and by `grep -rn 'recursive_triggers' swing/
> tests/` returning zero hits). **The approved COUNT (three) and the approved CRITERION (purely
> additive -- nothing rebuilt, nothing dropped, no existing row touched) both hold unchanged.**
> It is surfaced rather than absorbed because an approval given for one purpose should not be spent
> on another without its author seeing the swap. **EXCEPTION 2, the transactional
> `provenance_corrections` trigger replacement, is unaffected and remains APPROVED -- S4.5B.**

**PLAN-OWNED FINAL DECISIONS -- NOT held, NOT blocking execution, listed separately so the
distinction is never ambiguous:**

* **`horizon` refusal (S2.3.1) is a PLAN-OWNED DECISION and does NOT block execution.** RD's bound
  names invalidation "or above" and `horizon` ranks below it, so refusing on it is the plan's
  reading rather than his ruling -- taken fail-closed with its ground stated at the site. It is
  surfaced at his gate as a reading he may overturn, **which is a different thing from a
  dependency.**
* **S2.3.4** (the lapse force), **S8-L9** (the heuristic `fill` terminal) and **S8-L10** (the
  unauthenticated envelope's named residual) are DECLARED LIMITATIONS with their reasons, surfaced
  under the accepted-limitations contract -- not open questions.
* ~~**S2.7's tier-2 mechanism is a CHOICE the plan makes and STATES.**~~ **CARVED to 22-A2.** RD's
  ruling named the evidence CLASS and the four binary criteria; verification-on-a-git-artifact was
  the plan's realization of it, and **that realization is 22-A2's to present at his gate, not this
  arc's** (S12). Struck rather than deleted so the decision is visibly deferred rather than
  quietly dropped.
* ~~**S2.3.1a's same-session tie widening.**~~ **RULED 2026-08-24 -- fill-wins UNIFORM.** Struck:
  the question it asked has been answered, and **re-routing a ruled question is how a settled
  decision gets re-litigated.**

---

## S12. DEFERRED TO **22-A2 (PROOF MACHINERY)** -- carved, not deleted

**Option C, ratified by both directors 2026-08-24.** This section exists so 22-A2's brief can LIFT
its premise-set verbatim instead of re-deriving it. **RD's binding condition governs everything
below: the deferred rulings travel AS RULED, not as questions.**

### S12.1 THE SETTLED DOCTRINE 22-A2 ENCODES (it does NOT re-derive any of this)

1. **PRE-BARRIER ADMISSION REFUSES BY DEFAULT** (RD, 2026-08-24). 22-A implements this with no
   escape; 22-A2 adds the escape below.
2. **THE TIER-2 CLASS.** *An IMMUTABLE EXTERNAL contemporaneous record of the frozen values --
   recorded before the outcome was known, tamper-evident since -- matching the current candidate row
   on every compared field at the mandate grain.* Operator recollection does not qualify;
   writer-absence does not qualify. The correction row records the TIER, the evidence CITATION and
   the UNCOVERED WINDOW.
3. **THE VERDICT IS A BINARY CONJUNCTION OF FOUR, NOT A THRESHOLD** (RD). Admits **iff**: (1) the
   snapshot commit is an **ancestor of `origin/main`** -- replication is the actual tamper anchor;
   (2) its recorded date **strictly precedes the fill session**; (3) its recorded values **match the
   current candidate row at the mandate grain**; (4) the **uncovered window is computed and
   recorded**. **Depth and anchor-strength are RECORDED, NEVER verdict-bearing.**
4. **SINGLE ROUNDING AUTHORITY** (RD's amendment at the source, so 22-A2 inherits it already fixed).
   Criterion 3's comparison happens **entirely in ONE domain** -- either the service compares and
   SQL stores without rounding, or canonical pre-rounded values are stored and compared bytewise.
   **A Python-rounded value must never meet a SQLite-rounded value across an equality.** *"A
   truthful evidence row rejected by its own trigger over a half-cent rounding convention would be a
   false refusal wearing a precision costume."*
5. **A STORED GRADE IS AN ATTESTATION OF WHAT WAS VERIFIED AT WRITE TIME; A VERDICT IS COMPUTED AT
   READ TIME AGAINST THE AUTHORITY** (CHARC and RD, independently). Attestations carry the METHOD
   and an `evaluated_at`.
6. **REPLAY IS FAIL-CLOSED AND CONTEXT DRIFT IS NEVER DIVERGENCE** (RD). A replay re-evaluates the
   same four criteria; any criterion failing REFUSES. **Descendant counts GROW in a healthy repo**,
   so treating growth as staleness would refuse every re-derivation forever. Criterion 1 failing at
   replay means published history was rewritten -- the event that SHOULD void the evidence.
7. **THE TIME ANCHOR IS PRACTICAL, NOT CRYPTOGRAPHIC.** Git author/committer dates are
   caller-settable and a local `main` is rewritable; `origin/main` ancestry does the tamper-anchor
   work.
8. **CONTINUITY RUNS FROM THE FIRE SESSION TO THE READ, NOT FROM MINT** (CHARC). Acceptance can
   trail the fire -- RHI is the live proof -- so a gap between fire and mint is exactly as fatal as
   one between mint and read. **Any gap DEMOTES to tier-2, emitting the four-part conjunction shape
   rather than a bespoke variant.** `gap_era_reconstructed` names that state.
9. **NO NETWORK CALL INSIDE `BEGIN IMMEDIATE`.** Verification is a PREFLIGHT under an explicit named
   timeout; the transaction re-checks only DB-bound facts. *(The generalisation survives in 22-A at
   S10-F9.)*
10. **TRADE 25'S CORRECTION**, with its evidence re-derived at each use -- `docs/rd-state.md` at
    `9f315cc6`, author-date `2026-08-10T02:41:33-10:00`, line 57 *"Frozen at fire: pivot 53.98 /
    `initial_stop` 41.42"*, matching candidate 12284 at 2dp, fire run 136 `run_ts`
    `2026-08-07T17:30:02`, **uncovered window 2.38 days**, 175 descendant commits, remote-replicated.

### S12.2 INHERITED FINDINGS -- 22-A2's OPENING PREMISE-SET, WITH THEIR EVIDENCE

**The directors named ten; the triage below adds the round-8 items that travel, and dispositions
EVERY round-8 finding so none falls through the carve.** *(That class -- survivors-by-inertia -- has
been caught thirteen times on this arc, and a re-scope is the largest opportunity for it yet.)*

| finding | disposition |
|---|---|
| **R6-02** | TRAVELS. Continuity from fire to read; a `live_at_acceptance` link stays authoritative after a retirement. |
| **R6-03** | **SPLIT.** The THREE-valued tier travels with `gap_era_reconstructed`; **the two-valued CHECK and its eleven mirror sites STAY and are live in 22-A.** |
| **R6-04** | TRAVELS. Attestation semantics. |
| **R7-01** | TRAVELS. The interval has no implementable definition as ruled -- candidate identity, fire instant, `applied_at` typing all unresolved. |
| **R7-02** | **TRAVELS, and DISSOLVES for 22-A** (S2.4d.1). `epoch_id` insert order is unenforced -- real, and it lives where eras live. |
| **R7-03** | **SPLIT.** The hard-coded-tier defect **STAYS and is FIXED in 22-A** (the minting trigger derives, two-valued). The three-valued CASE travels. |
| **R7-06** | TRAVELS. `evaluated_at`, method, resolved remote SHA. |
| **R8-01** | TRAVELS. `run_ts` is a run-START stamp (`runner.py:608`), not the candidate-insert instant (`:1600`). |
| **R8-02** | TRAVELS. `applied_at` is not monotone / unique / server-stamped / non-future. |
| **R8-03** | TRAVELS. `through_ts` undefined + wrong clock domain; **rung 9 cannot be SQL-bound to a Python return value.** |
| **R8-04** | **DISSOLVES.** It existed only because read-time authority contradicted the stored tier; single-state restores the stored tier as rung 9's subject, so case 33's conservative refusal is simply correct. **Fourth dissolution on this arc.** |
| **R8-05** | **STAYS -- LIVE IN 22-A.** The `$.authorization` closure tests presence, not input fidelity, and the envelope guards have no per-guard discriminator. The rungs it covers survive the carve. |
| **R8-06** | TRAVELS with the conjunction. |
| **R8-07** | **STAYS -- LIVE IN 22-A.** `AcceptedLatchOrder` lacks `actual_limit_price`, so the broker-reality price guard cannot be implemented by the declared API. The envelope guards survive. |
| **R8-08** | **STAYS -- LIVE IN 22-A**, and reduced: the ladder must be re-derived against the smaller arc anyway. |
| **R8-09** | **STAYS -- LIVE IN 22-A**, and much reduced: with no tier-2, the exemption roster loses 32i-32k and 46a-46c entirely. `5b-pre` is still owed. |
| **R8-10** | **STAYS -- LIVE IN 22-A, and it is MINE to close now (RD, explicit).** The frozen-vs-live SQL binding in the citation trigger SURVIVES the carve (S4.3), so a Python-computes / SQL-validates price boundary remains. **Checked rather than assumed, which is what he asked for.** |

### S12.2b ROUND-13 AND ROUND-14 ITEMS ROUTED TO 22-A2 -- with their founding evidence, so the brief lifts them rather than re-deriving

**Operator-ruled 2026-08-31, and the ruling's ground is the AL-3 lesson stated correctly: the
principle was never *make every instrument exact*, it is *do not claim exact when you are not*.** A
walk DECLARED as a heuristic detector with its residual blindness named is honest; a walk WIDENED
and claimed closed is the same false claim this arc refused to ship at AL-3. Each item below was
declared in place, pinned in the direction that fails if the blindness ever narrows, and carved
here rather than widened a third time. *(The pattern that produced the ruling: each walk had
already been widened ONCE along the one axis its finding named, and the very next review round
produced five more spellings and two more shapes. Widening along the reported axis answers the
EXAMPLE, not the CLASS.)*

| item | what 22-A2 owes | founding evidence, MEASURED |
|---|---|---|
| **`22A-R13-02`** | **AN APPEND-ONLY RE-ATTESTATION DESIGN** for `fill_envelope_identity`: `UNIQUE(fill_id, envelope_raw, canonicalizer_version)`, a writer that APPENDS a current-grammar reading rather than leaving an older one in place, and version-addressed consumers. It is the only thing that closes L19 without inverting two clauses or manufacturing a refusal. | `canonicalizer_version` appeared ONCE in `0037`; SEVEN sites referenced the table; SIX consume a reading and NONE checks the version. Splicing `AND fei.canonicalizer_version = '<current>'` into the subject-reading clause of the real migration made a truthful citation over an agreeing older reading REJECT (`IntegrityError`) -- the authorize-then-abort direction. Declared at **L19 (AL-11)** with a closure-checked roster and an arming tripwire. |
| **`22A-R13-03`** | **SQL-TOKEN-AWARE SCANNING** in place of a regex, for the whole-tree "SQL never reads a fill envelope" walk. | SIX spellings measured blind, each pinned as a declared row in `tests/trades/test_22a_envelope_canonicality_sweep.py`: `JSON_EXTRACT(` (case), `json_extract (` (space), `->>` (operator, no function), a `CAST(...)` wrapper, a `"quoted"` identifier -- and a SIXTH found here rather than reported, **a read split across two ADJACENT PYTHON STRING LITERALS**, which is how every SQL string in `swing/**/*.py` is actually written. Zero production occurrences today (both whole-tree walks return empty on every run). |
| **`22A-R13-04`** | **CALL-FOLLOWING** for the exception-roster closure walk: resolve a handler's parser through local helper functions and through import aliases. | TWO shapes measured blind: a narrow handler moved into a `parse_blob` helper (found, then DISCARDED by the function-sized scope filter) and `from json import loads` + a bare `loads(...)` (not recognised as a JSON parse at all). Either restores the money-bearing unhandled-`RecursionError` path with every closure test green. |
| **`22A-R14-01`** | **A BEHAVIOUR COMPARATOR FOR THE CANONICALISER.** Bind `ENVELOPE_CANONICALIZER_VERSION` to a DIGEST of `canonical_envelope_identity` and every dependency its answer is a function of (`envelope_is_canonical`, both extraction helpers, their key constants), with an append-only `(version, digest)` history -- **the shape `DERIVATION_RULE_HISTORY` already runs at `swing/trades/cohort_provenance_correction.py:300-376` for `_derive`**, so this is a second instance of a pattern this codebase has already proven, not a new design. Then a canonicaliser edit without a bump FAILS THE SUITE. | **The arc is its own counterexample, measured.** `22A-R13-01` changed the answer (`canonical` -> `refused` for every non-`str` document, both arms measured in that commit); the constant did NOT move; the tripwire shipped in the very NEXT commit passed, because it compares a Python constant to a SQL COMMENT -- two hand-maintained copies of a LABEL. For six commits `0037` carried the claim *"a reading can only be stale if the constant MOVED"*, already falsified by its own arc. Declared at **L19 (AL-11)** and PINNED by execution: `test_DECLARED_a_behaviour_change_WITHOUT_a_bump_is_invisible` restores the retired predicate, asserts the answer moved and the label did not, and calls the tripwire -- green. It is the hand-maintained-roster class (four rosters in this arc) arriving on a VERSION CONSTANT. |
| **`22A-R14-03`** | **OCCURRENCE-LEVEL SQL REFERENCE COUNTING** for the `fill_envelope_identity` closure walk: `finditer` over comment-blanked text retaining each match's offset, rather than one `search` per line. | MEASURED on the real migration: splicing a SECOND `FROM fill_envelope_identity` onto an EXISTING reference line raises the OCCURRENCE count by one and leaves `_references` unchanged, so an unmarked eighth consumer passes both the count and the interleaving assertion. It is `22A-R12-04`'s per-line-versus-whole-body class reappearing INSIDE the instrument written in the round that declared it. Declared + pinned at `test_DECLARED_two_references_on_ONE_LINE_count_as_one`. |
| **`22A-R14-04`** | **ALIAS-SCOPED PREDICATE DETECTION** for `_span_checks_version`: associate each reference with its alias and require a predicate on THAT alias, instead of a bare substring test over the span. | MEASURED on the real migration, two rows: an inert string literal `'canonicalizer_version' <> ''`, and an unrelated alias's `zz.canonicalizer_version`. Either flips `rung6_population_has_been_read` from VERSION_BLIND to VERSION_CHECKED. **Direction stated precisely because it bounds the exposure:** on its own this fails LOUDLY (declared vs measured disagree), so the SILENT hole needs the roster edited to match -- at which point L19 asserts a check that does not exist. |
| **`22A-R14-05`** | **STATEMENT-LEVEL (AST + SQL-token) INSPECTION** of the Python half, in place of the single-line `SELECT`-and-column rule. | MEASURED against `_version_projections`, the SAME function the production assertion calls: a multiline projection and a multiline `WHERE` are both invisible -- and that shape is not exotic, it is how EVERY SQL string in `swing/**/*.py` is written, as adjacent literals one per line. A control pins that the single-line form is still caught, so declared blindness can never be confused with a walk that quietly stopped working. |
| **`22A-R14-06`** | **RE-ATTESTATION OR REFUSAL OF A DISAGREEING STORED READING** -- the material half of AL-11. Subsumed by the append-only re-attestation design already carved at S12.4; recorded separately because it is what a fix has to make FAIL. | The AL-11 pin monkeypatched only the version LABEL, so the stored answer AGREED with today's and the case measured the BENIGN acceptance. Fixed IN THIS ARC rather than routed -- the missing case had a determinate shape (SS-13's treatment: rename the pin to what it measures, then write the case its name claimed). `test_THE_DECLARED_LIMITATION_a_stale_DISAGREEING_reading_is_ACCEPTED` now plants a genuinely disagreeing answer through the production writer; **22-A2 owes the refusal that makes it fail.** |
| **`22A-R13-05`** | **PREDICATE-SHAPE ASSERTIONS** for the AL-3 closure (each SQL_BOUND clause asserts its authoritative operand and predicate), **REAL-INPUT DISCRIMINATORS** (mutate the production roster/migration, not a local reconstruction), and **PINS VALIDATED THROUGH COLLECTION** rather than by text-searching for `def`. | `_input_bound()` asks only whether a clause's span contains a subquery or a non-probe `NEW.` reference. Pinned by execution: strip the `ORDER BY ... LIMIT 1` that makes rung 3b *the LATEST* validity child, leaving its `SELECT`, and the walk still answers True. The reviewer looked for a mislabelled member and found none, so this is test QUALITY, not a demonstrated acceptance. *(The pattern to apply: `tests/data/test_22a_canonicalizer_version_closure.py`, written after it, splices into the REAL migration text.)* |

### S12.3 WHAT 22-A2 ALSO INHERITS AS SCHEMA

The `cited_frozen_value_evidence_json` column * the third tier value `gap_era_reconstructed` * the
`barrier_state` / era columns on the epoch table * the third and fourth epoch triggers * the
`--frozen-value-evidence` CLI option and its manifest-pin bump.


---

## S13. THE EXECUTING ARC'S OPENING PREMISE-SET -- round 9's thirteen, EVERY ONE DISPOSITIONED

> **PLANNING IS CLOSED. The operator ruled it complete on 2026-08-24, CHARC endorsing "without
> reservation," on the argument that the loop's own evidence had become the case against continuing
> it:** the 10,000-value rounding scan, the 24-row live incidence, the `recursive_triggers` grep and
> `22.13 = 22.13` are **findings a TEST catches in seconds and a review round catches one at a
> time.** *The review never failed -- 110 findings across nine counted rounds, zero oscillation, not
> once. It is the wrong instrument for what remains.*
>
> **THREE CRITICALS AND ONE DIRECTOR-ADDED ITEM WERE FIXED IN THE PLAN. THE REMAINING NINE MAJORS
> AND ONE MINOR ARE RECORDED HERE, WITH THEIR EVIDENCE, AS THE EXECUTING ARC'S OPENING
> PREMISE-SET** -- the same verbatim-liftable mechanism S12 uses for 22-A2, ratified by CHARC for
> this purpose. **Nothing falls through: a close-out is the last and largest survivors-by-inertia
> opportunity this arc will offer**, so every one of the thirteen is listed, including the ones
> already closed, with WHERE it landed.
>
> **AN INHERITED FINDING IS A PREMISE, NOT A SUGGESTION.** Each carries its evidence so the
> executing implementer can verify it rather than trust it -- and **two of them falsify cases this
> plan itself specifies.** They are recorded exactly as found. *An executor inheriting a
> known-wrong case is far better off than one inheriting a silent one.*

### S13.1 FIXED IN THIS PLAN -- verify the repair, do not re-derive it

| id | sev | where it landed |
|---|---|---|
| **22A-R9-01** | CRITICAL | **S2.4d.1, rewritten.** The `sqlite_master` check verified NAMES only, so same-name NO-OP triggers returned 2 while `candidates` was fully mutable -- and cases 50a-50c only ever removed names, so all three passed the fail-open implementation. **CHARC ruled the repair and owned the origin as his requirement rather than its encoding:** compare the trigger **BODY** against a **VERBATIM PINNED COPY**, per the **T1b precedent** already running at `swing/integrations/schwab/auth.py:1519` (`_V3_SCHWABDEV_DDL`). **Normalization is whitespace-only; NO semantic-equivalence judgment** -- a comparator that decides two bodies are "equivalent" is a new free dimension (S3.8). **Cases 50a-50e**, where **50d** plants the same-name no-op and **50e** pins normalization in both directions. |
| **22A-R9-03** | CRITICAL | **S5.2-S5.5 + task 9.** "The route decides nothing" DELETED a live production rejection: the PE-anchor / manual-origin guard exists ONLY at `swing/web/routes/trades.py:1261-1268`, and `record_entry` has no equivalent (`swing/trades/entry.py:264`, `:352-373`). **The guard is RELOCATED into `record_entry`, inside `BEGIN IMMEDIATE`** -- which is also where it belongs, since its input `derive_trade_origin` reads the world the write lands in. **Case 37c** pins the STABLE no-link refusal that 37b (a race) cannot. |
| **22A-R9-11** | CRITICAL | **S7, restructured.** Migration `0037` was staged across three commit-tasks while task 2 tested idempotence. **The runner applies a version once and only when strictly greater** (`swing/data/db.py:1965-1966`, `:2102` -- read on disk), so once any dev DB recorded v37 the later additions would **never run**, invisibly, with CI green. **Task 2 is now the WHOLE migration in ONE task with ONE version bump; tasks 3 and 11 keep only the Python that reads it.** The rule is general: **a versioned migration file is an ATOMIC deliverable.** |
| **NEW -- CHARC's generalisation** | CRITICAL-grade | **S4.5-replace.** He amended the CLAUDE.md `REPLACE` gotcha off this arc's epoch finding on the ground that **any DELETE-trigger barrier in this codebase is fail-open to `REPLACE`**, and directed a check of the `candidates` barrier itself. **It has the same hole, and worse: `candidates` carries TWO conflict targets** (`id INTEGER PRIMARY KEY` and `UNIQUE(evaluation_run_id, ticker)`, `0001:24-41`). Measured at production settings: `INSERT OR REPLACE` **moved the id 12284 -> 12285, rewrote pivot/stop, and CASCADE-WIPED `candidate_criteria`** -- the exact id-reuse catastrophe S4.5A cites as the DELETE half's whole reason, **reached with both barrier triggers present, canonical and unfired, so S2.4d.1's body check cannot see it.** Closed with a CONFLICT-SCOPED `trg_candidates_no_replace`, verified to leave ordinary nightly INSERTs untouched. |

### S13.2 INHERITED -- nine MAJOR, one MINOR, with the evidence to verify each

> **NONE of these is adjudicated.** The stopping rule reserved that decision, and it now belongs to
> the executing arc. Where a finding contests something this plan asserts, **the plan's text has NOT
> been quietly changed to agree with it** -- the disagreement is left visible on both sides.

| id | sev | the finding, and the evidence to check it against |
|---|---|---|
| **22A-R9-02** | MAJOR *(reported CRITICAL; downgraded ONLY because R9-01's repair now sits between it and any admission -- the boundary defect itself is unrepaired)* | **S2.4d and S4.5C disagree at the epoch boundary.** S2.4d: at-or-below the boundary = **pre**-barrier. S4.5C, inside CHARC's lifted quote: *"rows at or after it do [admit]"*. A candidate whose id **EQUALS** `max_candidate_id_at_barrier` already existed when the barrier was installed, so it is pre-barrier -- but the S4.5C wording directs an executor to `>=` and stamps it `live_at_acceptance`. **Case 38 cannot catch it:** it only requires the Python reader and the SQL twin to AGREE, and two identically-wrong `>=` implementations agree. **Fix direction: the case must assert the EXPECTED TIER at each of below / equal / above, not merely agreement.** |
| **22A-R9-04** | MAJOR | **Case 30d models a SCHEMA-IMPOSSIBLE order, and its justification is false.** `0033:464-469` CHECKs that every `accepted_by_broker` row carries `actual_limit_price IS NOT NULL`; place rows' actuals are NULL-constrained at `:611-614`. **The plan's "four of the five live intent rows carry NULL" is a correct measurement with a wrong inference** -- those four are `place` intents and can never back an accepted link. A hand-constructed dataclass can still exercise the pure function's defensive NULL handling, but **30d is not a schema-backed case and does not discriminate the production path.** *(This falsifies work authored in the same leg that added it.)* |
| **22A-R9-05** | MAJOR | **Case 34g does not discriminate -- verified by execution.** With frozen = live = `22.125`, the forbidden `round(...,2) = round(...,2)` evaluates `22.13 = 22.13` -> **ACCEPTS**, so the prohibited implementation passes the case written to catch it. **A discriminating fixture needs two raws in ONE Python bucket and TWO SQLite buckets** -- e.g. `22.125` / `22.1249` (Python `22.12 == 22.12` admits; SQLite `22.13 <> 22.12` rejects). **Also: the `round(` grep gate is underspecified** -- a literal match does not reject `ROUND(`, `round (`, or formatting variants unless the test normalizes case and whitespace. **S4.3a's RULE is sound; both of its stated DEFENCES are not.** *(Also authored in the same leg.)* |
| **22A-R9-06** | MAJOR | **The SQL-bound / service-validated split is drawn in the wrong place, and L17's reason is factually wrong.** L17 says the five envelope guards rest on *"operator-submitted values that no subquery can reach."* **By CORRECTION time those values are PERSISTED:** `provenance_corrections` cites `entry_fill_id_at_correction` and the shipped trigger already reaches that fill and its trade (`0036:608-619`); the fill carries quantity, price, `fill_origin` and `schwab_source_value_json` (`swing/data/models.py:383-399`); the validity/link rows carry accepted quantity and limit. **So SQL CAN bind the five guards' inputs**, and case 49j pins an AVOIDABLE weakness. **Rung 8 genuinely depends on external derivation state; the envelope guards do not belong in its class.** |
| **22A-R9-07** | MAJOR | **S4.3 never specifies the `$.authorization` schema it calls closed and exact.** No key names, no `input` object shapes, no required types, no per-rung binding. **"Derived from the 33-member decline-reason roster" does not determine it:** eleven rungs plus five guards do not map one-to-one onto 33 reasons, and several rungs emit multiple reasons. Examples of the form *"a substituted broker order id in rung 1 ... and so on"* cannot yield an exact migration closure list. **Two executors can produce incompatible schemas while both following the document**, so the migration and cases 48/49 are not deterministically implementable as written. |
| **22A-R9-08** | MAJOR | **Cases 9/9b can no longer reach their own verdict.** They plant drift by *"dropping the trigger inside the test transaction"* (S4.5C) -- but rung 9 now REFUSES `barrier_not_installed` whenever a barrier is absent **or altered** (S2.4d.1, now stricter still after R9-01). So the fixture tests the integrity guard instead of `frozen_value_drift`. **Fix direction: re-create the canonical trigger after planting the mutation and before authorization** -- which the body-comparison check makes exactly expressible, since a byte-identical restore now passes by construction. |
| **22A-R9-09** | MAJOR | **S7 still non-topological in two places** *(the ladder was restructured for R9-11; this finding was NOT re-verified against that restructure and must be re-checked first)*. As reported: (1) **task 2 accepts 50a-50c**, which are full admission/refusal outcomes needing the link table, the authorization service and the resolver -- **the R9-11 restructure already moved 50a-50e to task 3, which addresses this half and should be confirmed**; (2) **task 4 accepts 4c-i, 4c-ii and 15f**, which need per-ticker live-competitor classification -- `mandate_alive_at` (task 6) and rung 8 (task 6a), **the rung task 4 now explicitly disclaims.** Half (2) is UNADDRESSED. |
| **22A-R9-10** | MAJOR | **The case-to-task closure check is itself false and under-specified -- the instrument added to end the class joined it.** Concretely: **case 17 and case 31 appear in NO acceptance cell** *(the R9-11 restructure added both to task 11; re-verify)*; **task 10 accepts 37 but not 37b**; **task 6 still accepts case 11b, which S3.7 and S6 mark REMOVED**; task 2 accepts case 33, sourced outside the collector's declared source set; S3 contains carved/struck ids (32f, 40a-40f, 46a-46c, deleted 28d) the "static walk" does not say how to exclude; and acceptance cells use **RANGES and implicit families** (`1-6`, *"their `-pre` twins"*) that the collector claims to read as ids. **Either the check fails this plan immediately or it needs an unstated semantic parser.** |
| **22A-R9-12** | MAJOR | **Two build-directing carve residuals the sweep missed.** **S0(3), in THE HEADLINE**, still asserts a tier-2 class exists, describes its evidence columns and says trade 25 qualifies -- with no carve marker. **S1.8** still calls the monkeypatched trade-25 post-values *"the S9 live-application outcome"* and says they *"bound Task 10"* -- but S9's outcome is now `pre_barrier_unproven` with no correction, and task 10 is the route extension. **Neither is a harmless historical note: S0 is the headline and S1.8 explicitly directs a task.** |
| **22A-R9-13** | MINOR | **Migration idempotence is wrongly credited to the `BEFORE INSERT` trigger.** A second `run_migrations` never re-enters 0037 -- the version gate returns first (`swing/data/db.py:1965-1966`). Cases 35c/35p validly test the trigger; **the twice-run migration test does not prove that property and should not be cited as doing so.** |

### S13.3 HOW THE EXECUTING IMPLEMENTER SHOULD USE THIS

1. **Re-verify before building.** Every row above carries its `file:line` or its executable check.
   **A premise belongs to the CODE, not to whoever last described it** -- including this plan, and
   including the four repairs in S13.1.
2. **R9-09 and R9-10 were reported against the PRE-restructure ladder.** The R9-11 fix moved cases
   between tasks and may have closed parts of both. **Re-run the check before acting on either**, and
   **do not assume the restructure closed what it happens to touch.**
3. **R9-04 and R9-05 falsify cases this plan specifies.** Fix the FIXTURE, keep the CLAUSE: 30d's
   NULL branch is still worth a pure-function test *(as a defensive-handling test, not a
   schema-backed one)*, and 34g's rule is still right while its geometry is wrong -- use
   `22.125` / `22.1249`.
4. **R9-07 is the one that blocks a deterministic build.** The `$.authorization` schema must be
   written out -- sixteen key names, each `input` shape, each binding -- **before task 2 writes the
   migration**, because the closure list is part of the trigger.
