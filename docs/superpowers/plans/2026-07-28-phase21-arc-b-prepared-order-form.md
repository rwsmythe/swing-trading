# Phase 21 Arc B — the prepared-order form (LOG-ONLY) + the execution-parity ledger — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Put the framework's computed entry order in front of the operator **with its derivation visible**,
capture his response in a three-state action space (ACCEPT / DECLINE+reason / NO-ACTION) sub-split by
objective view telemetry, and persist both sides plus a recomputable per-field delta in an execution-parity
ledger RD reads monthly. **NOTHING is sent to the broker in this arc.**

**Architecture:** Two new PURE modules under `swing/latches/` (the Phase-12 classifier convention — no DB, no
network, no transactions): `order_intent.py` computes the prepared order + the per-field delta;
`classification.py` turns (latch, views, intents, telemetry health) into a disposition and an execution-parity
report. Migration `0033` (v32 -> v33) adds ONE new table (`latch_order_intents`) and REBUILDS
`latch_view_events` to add `surface` + the THREE actionability columns (`actionable_at_first_view`,
`actionable_at_last_view`, `actionable_ever_viewed` — §C.1) and re-key its UNIQUE onto the bridge key. The web layer extends the EXISTING panel VM/route/template (no new base-layout VM field)
and adds exactly one new endpoint, `POST /latches/intent`. A read-only CLI report (`swing latches parity`)
makes the ledger a measurement rather than a table.

**Tech Stack:** Python 3.14 / SQLite (`sqlite3`) / FastAPI + Starlette 1.0 + Jinja2 + HTMX 2.x / click / pytest.

---

## Global Constraints

Every task's requirements implicitly include this section.

- **Branch/base:** worktree `.worktrees/phase21-b-prepared-order`, branch `phase21-b-prepared-order`, base
  `1955aa59` (main at 21-A merge; schema v32). All work on this branch; the ORCHESTRATOR merges.
- **Commits:** conventional, carrying the task id (`feat(latches): Task 3 — ...`). **ZERO `Co-Authored-By`.
  No `--no-verify`. No amend.** Keep the final `-m` paragraph plain prose (trailer-parse hazard).
- **TDD:** failing test -> SEE it fail -> minimal implementation -> SEE it pass -> commit. One red/green cycle
  per task.
- **Lint:** `ruff check swing/` stays clean. `line-length = 100`, `select = ["E","F","W","I","N","UP","B","SIM"]`.
- **ASCII discipline:** no non-ASCII glyphs in any string that can reach stdout (the CLI report is a live
  stdout surface — this binds hard there).
- **Phase isolation:** **NO `swing/trades/` EDITS.** `swing/trades/equity.py` is IMPORTED read-only
  (`current_equity`, `sizing_equity`, `list_all_exitshape_via_fills` — all pure/SELECT), exactly as
  `swing/latches/reader.py` already imports `swing/trades/voided_trades.py`. The `swing/data/` additions
  (migration `0033`, `swing/data/repos/latch_order_intents.py`, the `LatchOrderIntent` model + the `surface`
  and the three `actionable_at_first_view` / `actionable_at_last_view` / `actionable_ever_viewed`
  fields on `LatchViewEvent`, and the
  `swing/data/db.py` version bump + backup gate) are the scoped
  addition the 21-B brief's SCHEMA TRIPWIRE authorizes — the same carve-out 21-A took for `0032`.
- **NO CARDINALITIES, NO HAND-KEPT INSTANCE LISTS — STATE A ROSTER AND DERIVE FROM IT.** This plan wrote a
  number where it could have written the rule for obtaining the number, and **a count of its own contents was
  wrong in five consecutive review rounds** (`seven CHECKs` -> eight, `six keys` -> seven, `ten enums` ->
  eleven, `four deltas` -> five, `two columns` -> three). That is a MECHANISM, not bad luck: naming a set by
  cardinality-plus-inline-list in N places means every edit invalidates N-1 of them, so the artifact generates
  review findings indefinitely and independently of whether it is CORRECT. The binding rule:
  - **Every set gets ONE authority** — a named frozenset in `swing/latches/constants.py`, or a machine-readable
    artifact (the migration's own DDL, the `json_remove` path list, `PRAGMA table_info`). The rosters this
    plan names are `LATCH_DISPOSITIONS`, `R_BUCKETS`, the five bucket frozensets and their union
    `_RULED_DISPOSITIONS`, `LATCH_BROKER_SNAPSHOT_KEYS`, `DERIVATION_NULLABLE_ON_DECISION`,
    `LATCH_BROKER_SNAPSHOT_{RENDER,PERSISTED}_BRANCHES`, and the §C.1 rebuild-delta list.
  - **Every other site REFERS to the roster by name and states NO count.** "Every member of X", never "all
    eleven X".
  - **Every test ITERATES the roster** rather than repeating its members, so a set that grows gains its cases
    automatically instead of needing a bullet edited.
  - **Where a number must appear for a human, it is a DATED MEASUREMENT, labelled as such** (the §J audit
    counts), never an invariant a test asserts.
  - **Where a list must be maintained at all, use the ANNOTATED-MANIFEST shape** (Task 1's enum manifest):
    every parsed item must be classified, and an UNCLASSIFIED item FAILS the test. Silence is the failure
    mode; annotation is the fix.
- **#11 one-commit multi-mirror discipline:** every CHECK enum in `0033`, its Python frozenset in
  `swing/latches/constants.py`, and the dataclass `__post_init__` validator land in **ONE** task/commit
  (Task 1). No repo guard may re-declare an enum; `swing/data/models.py` IMPORTS the frozensets (the 21-A
  `_LATCH_VIEW_STATES is LATCH_STATES` precedent, pinned by an identity test).
- **Backup gate:** it FIRES on **`current_version == 32 AND target_version >= 33`** — STRICT equality on the
  pre-version per the `pre_version == (target - 1)` gotcha, NEVER `<=`. (The shipped clause expresses that as
  an early return, `if target_version < 33 or current_version != 32: return`; the plan's first draft quoted
  only that inverted guard, which reads as the fire condition and is the opposite of it — Codex R15 MAJOR 3.)
  The canonical test oracle is the four-cell matrix `(32,33,True) / (31,33,False) / (32,32,False) /
  (33,33,False)`. Copied VERBATIM from
  `_phase21_arc_a_backup_gate` (`swing/data/db.py:1575-1612`). The pre-migration expected-table
  set is derived deterministically: `PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES =
  PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES | {"latch_view_events"}` (0032 added exactly that one table).
- **NO Schwab WRITE call of any kind.** This arc logs intent only. The write path is 21-C behind an
  operator-signed L2 endpoint diff. Pinned **behaviourally as well as textually** (Codex R2 MAJOR 3 — a
  name-list grep is the D21 decay class: it passes while a renamed or newly-added mutator sails through):
  - **(i) TRANSPORT-LEVEL, DENY-BY-DEFAULT — the primary pin (Codex R11 MAJOR 2).** A name-matched mutator
    list is not exhaustive: `submit_order`, or any future write API whose name misses the verb heuristic,
    sails straight through while the test passes green. So the pin is placed where names cannot matter — the
    HTTP transport. The test installs a stub over the session schwabdev issues requests through and
    **fails on ANY non-GET request to the Schwab Trader API host**, then drives `GET /latches`, every branch
    of `POST /latches/intent` and `POST /latches/orders` through TestClient. Read paths are GETs and pass;
    anything that writes fails REGARDLESS OF THE METHOD NAME THAT ISSUED IT. Scoped to the Trader API host so
    an OAuth token refresh (a legitimate POST to the auth endpoint) is not a false failure — and a test
    asserts that carve-out is host-scoped, not verb-scoped, so it cannot be widened by accident.
  - **(i-b) METHOD-LEVEL, secondary.** The introspection sweep is retained as a second net: enumerate every
    public callable on the installed `schwabdev.Client`, subtract an EXPLICIT read-only allowlist, and
    monkeypatch the REMAINDER to raise. Deny-by-default, so a schwabdev upgrade that adds a write API is
    covered the day it lands and the allowlist edit is a deliberate act with a reviewer.
  - **(ii) SEAM.** The same test asserts the intent flow never borrows the client at all —
    `app.state.schwab_client_holder.borrow` is instrumented and must have ZERO calls across the POST.
  - **(iii) LEDGER.** `schwab_api_calls` row count is unchanged across `POST /latches/intent`.
  - **(iv) TEXTUAL, retained as a cheap belt only.** The grep for the four names anywhere under `swing/`.
    It is explicitly NOT the enforcement; (i)-(iii) are.
  - The shipped `POST /latches/orders` fragment is in the same behavioural sweep: it is allowed to READ
    (`get_account_orders`) and must still trip no mutator.
- **A5 (inherited from 21-A):** no new field on `base.html.j2` or on any existing base-layout VM. `LatchPanelVM`
  and `LatchRowVM` extend. **Every new `LatchPanelVM` field MUST be added to
  `swing/web/view_models/latches.py:PANEL_SPECIFIC_FIELDS`** or `declared_banner_fields()` mis-reports and the
  cross-VM banner drift-pin (`tests/web/test_topbar_cross_vm_consistency.py`) breaks.
- **A6 (inherited from 21-A):** every builder path degrades VISIBLY and never 500s. The prepared-order block is
  a strictly-additive part of a builder that already carries a catch-all.
- **A4 (inherited from 21-A):** `GET /latches` writes NOTHING. The prepared-order form is RENDERED on the GET
  and only its SUBMISSION writes. `POST /latches/intent` is the only new write path.
- **Suite:** run the FULL fast suite (`python -m pytest -m "not slow" -q`) to green BEFORE the Codex review, and
  again at the end.
- **Editable-install gotcha:** for CLI checks from the worktree use `PYTHONPATH=. python -m swing.cli latches
  parity`. `pytest` from the worktree cwd is unaffected.

---

## A. DECISIONS FOR RD. A.1 and A.1.6 are RULED; A.2 and A.3 remain open.

### A.0 THE GOVERNING MEASUREMENT PRINCIPLE (RD, 2026-07-28 — stated once, applied everywhere)

> **DO NOT MERGE CATEGORIES THAT DIFFER IN EVIDENCE KIND, EVEN WHEN THEY AGREE IN OUTCOME.
> Merge only what is measured the same way.**

RD records this as its **THIRD application in this arc** and asks that it stop being rediscovered case by
case. Every merge question in this plan resolves against it, so it is stated here rather than re-derived at
each site. Its three ruled instances:

| the two categories | they AGREE in outcome | they DIFFER in evidence kind — so they stay separate |
|---|---|---|
| `pre_telemetry` vs `away_unseen` (§A.1.1) | both exclude the fire from the discipline signal | *"the instrument did not exist"* is not *"the instrument looked and saw nothing"* |
| `attested_was_away` vs `away_unseen` (§A.1.6) | both mean non-judgment non-action | **testimony is not telemetry** |
| a stale-close MISMATCH vs MATCH (§B, 21-G) | same input, same price | one is an alarm you MAY raise; the other is a claim you may NOT assert |

The practical test the principle gives an implementer: before collapsing two labels because they route to the
same bucket, ask **how each was MEASURED**. If the answers differ, the labels stay — and if they must be
summed for a reader, the sum is reported as its own explicitly-named figure rather than by erasing the
distinction upstream.

### A.1 THE ACCEPTANCE TEST WAS VACUOUS AS WRITTEN — RULED BY RD 2026-07-28

**The brief's §3 binding acceptance test:** *FTRE fired 07-20 during the operator's vacation -> the panel shows
viewed=NO across the armed window -> it classifies AWAY, is EXCLUDED from the discipline signal, and its +1.22R
lands in the away bucket.*

**Verified on the live DB + filesystem, 2026-07-28:**

| fact | evidence |
|---|---|
| `latch_view_events` holds **ZERO rows** | `SELECT COUNT(*)` on `~/swing-data/swing.db` |
| the table was **created today** | pre-migration backup `~/swing-data/backups/swing-20260728T111453.db` (0032 ran 2026-07-28 11:14:53) |
| the earliest `view_session_date` the beacon could EVER write is **2026-07-29** | `action_session_for_run(datetime(2026,7,28,11,14,53))` -> `2026-07-29` (the beacon writes `derivation.horizon_session`, which is that value) |
| FTRE armed **2026-07-20**, horizon **2026-08-31** | `candidates.id=11261`, eval run 121, pivot 18.34 / stop 14.88; `session_offset(2026-07-20, 30)` -> `2026-08-31` |
| FTRE's armed window is therefore **PARTIALLY instrumented**: sessions 07-20..07-28 can never carry telemetry; 07-29..08-31 can | arithmetic over the two rows above |

So "viewed=NO across the armed window" is **true of FTRE and equally true of every latch that has ever
existed**, for a reason that has nothing to do with the operator's behaviour: the instrument did not exist.
A naive scheme that maps *no view rows -> AWAY* passes this test **identically whether the operator spent the
week on a beach or staring at the panel**. It is not a discriminator.

Worse, it is **unstable in the flattering direction**: FTRE stays armed until 2026-08-31, so a single panel
open on any session from 2026-07-29 onward writes a view row and flips FTRE out of AWAY — re-classifying a
week the operator genuinely spent away, on the strength of behaviour AFTER that week.

**This collides with a decision already on the record.** At Phase-21 scoping CHARC named the sequencing trap
(`phase21-scope-charc.md` line 49) and RD ruled telemetry into 21-A to minimise it. CHARC's named fallback for
fires still in the gap was: *explicitly stamped **pre-telemetry** and excluded honestly — never defaulted.*
FTRE is exactly such a gap fire. RD's own two rules decide this: **unclassifiable is LOST data, not uncertain
data**, and **an honest instrument does not flatter its subject.**

#### A.1.1 RD's ruling, encoded

**RULED BY RD 2026-07-28. This section is no longer a proposal — it is the ruling, encoded.** RD confirmed
the acceptance test is vacuous and owned it as his own error (*"I wrote an acceptance test whose subject could
not have produced a discriminating answer"*). His three rulings are §A.1.1-§A.1.3 below; §A.1.5's two-branch
gate is CLOSED and the losing branch is DELETED.

**A TELEMETRY EPOCH, and a coverage-aware classification driven by RD's table.**

```
LATCH_TELEMETRY_EPOCH_SESSION = date(2026, 7, 29)
    # The first action session for which a latch_view_events row could exist.
    # Migration 0032 applied to the live DB at 2026-07-28T11:14:53 (backup
    # swing-20260728T111453.db) and the beacon writes
    # action_session_for_run(now), which at that instant was 2026-07-29.
    # A HISTORICAL FACT, not a derived quantity -- see A.1.3 for why it is a
    # constant and not a MIN() over the table.

covered_window(latch)  = [max(anchor, EPOCH), clear_or_horizon_session]
uncovered_window(latch)= [anchor, min(EPOCH, clear_or_horizon) )   # may be empty
```

**RULING 1 — `pre_telemetry` IS A DISTINCT CLASSIFICATION, NOT A FLAVOUR OF AWAY (RD, verbatim):**

> *"AWAY means the instrument looked and saw nothing. PRE_TELEMETRY means the instrument did not exist. Those
> are different facts, and collapsing them lets an absence of apparatus masquerade as an observation about the
> operator."*

**RULING 2 — THE PARTIAL-COVERAGE RULE (RD, verbatim, and the load-bearing one):**

> **A view record in the covered portion ESTABLISHES awareness; its absence over a partially-dark window
> ESTABLISHES NOTHING.** Positive evidence is dispositive; absence of evidence from a period with no
> instrument is not evidence of absence.

**THE RULED TABLE — encoded LITERALLY as a lookup table, not as nested conditionals (§E.0):**

| window coverage | view record in the covered portion | disposition |
|---|---|---|
| FULLY covered | — | classify normally (accepted / declined / away / lapse) |
| PARTIALLY covered | **YES** | awareness ESTABLISHED — classify on it |
| PARTIALLY covered | **NO** | **`pre_telemetry`** |
| FULLY pre-telemetry | — | **`pre_telemetry`** |

**Note RD's ruling COLLAPSES the plan's drafted `partial_telemetry_unresolved` into `pre_telemetry`.** The
draft split them to keep the reasons distinct; RD ruled one disposition, because the reason is the SAME in
both rows — *the instrument was not there* — and a second name would imply a distinction the evidence does
not support. The plan follows the ruling: `partial_telemetry_unresolved` is DELETED from
`LATCH_DISPOSITIONS`.

**The property that makes the ruling correct, which the implementation MUST preserve:** the classification can
only move from unknown toward a POSITIVE fact, never toward a negative inference drawn from a dark period.
That is what resolves the instability §A.1 raised — **FTRE cannot flip to `away_unseen` next week because of
something that happens after the window it describes**, since only a view record INSIDE the covered portion
can move it, and that record establishes awareness rather than absence. A test asserts this directly:
adding a view row to a partially-covered latch moves it OFF `pre_telemetry` only into an awareness-established
cell, never into `away_unseen`.

**The under-claiming coupling RD ratified in 21-G applies here verbatim:** *permission is not obligation, and
withholding is never a false all-clear SO LONG AS THE REDUCTION IS LABELLED.* Every under-claim this plan
makes is therefore labelled at the surface that makes it — `pre_telemetry` and `never_actionable` render their
reason on the card, the withheld prepared-order form renders `withheld_detail` (§D.3), the withheld away rate
renders its `withheld_reason` and counters (§F.2), and the mandate-form check renders its per-latch note
(§H). An UNLABELLED reduction would be a quiet all-clear by omission and is the failure mode, not the
under-claim itself.

#### A.1.2 What this does to FTRE, stated plainly

**FTRE classifies `pre_telemetry`, not `away_unseen`** (RD ruling 2, the partial-no-view row).

- **The outcome RD asked for is preserved:** FTRE is EXCLUDED from the discipline signal and its +1.22R is not
  scored against his judgment. On that, the brief's test and this plan agree.
- **The outcome that changes is the BUCKET.** The away bucket is not merely "excluded" — it is the numerator
  of the AWAY RATE, which RD named as *the quantified business case that will justify or kill stage-3
  auto-place*. Putting an unclassifiable fire in it **inflates the exact number that argues for automating the
  operator's entries** — which is the corruption B5's telemetry-health gate exists to prevent and the same
  corruption the 21-F proposal §4 flags from a different direction. Following the brief's test literally would
  make 21-B commit, in its very first observation, the bias its own §2.5 forbids.
- So: **`unattributable_r` is a THIRD bucket** alongside `away_r` and `decision_r`. FTRE's +1.22R lands there,
  which is exactly RD's ruling-3 requirement that it *"must not be scored against the operator's judgment."*

**The live consequence, stated so nobody is surprised at the GUI witness:** on today's substrate **every live
latch is `pre_telemetry`** — FTRE anchored 07-20 and VSTS anchored 07-27 both predate the 2026-07-29 epoch
(RD: *"VSTS re-fired 07-27, also pre-telemetry by a day"*). The instrument's first fully-classifiable
observation is **the next A+ fire on or after 2026-07-29**. That is the honest answer to "when does this start
measuring", and it is one fire away.

#### A.1.3 Why the epoch is a constant and not `MIN(view_session_date)`

Deriving the epoch from the data is actively wrong: with zero rows it is undefined, and once rows exist it
would drift FORWARD every time the operator goes quiet — so a genuinely-away fire would be re-labelled
"uninstrumented" precisely because he was away. That is the flattering direction. The constant is a historical
fact with a filesystem-timestamped provenance, and it follows the in-tree precedent for exactly this shape:
the 18-D research monitor baselines check #1 on the hard-coded `date(2026, 6, 13)` 18-A boundary. The
derivation takes it as a keyword argument so tests set their own; production passes the constant.

#### A.1.4 The substitute discriminating tests (Step-5's requirement)

**RULING 3 (RD): FTRE IS RETIRED AS THE DISCRIMINATING TEST, BUT THE REAL-DATA ANCHOR STAYS.** The
discriminating test becomes a **seeded-telemetry fixture** inside a FULLY-covered window — necessary because
no real fire is yet fully covered — while FTRE keeps a CORRECTED real-data assertion. RD: *"Do not lose the
real-data anchor; correct what it asserts."* Three tests:

- **T-A (the REAL-DATA ANCHOR, corrected — RD ruling 3).** FTRE's real numbers, real anchor 2026-07-20, epoch
  2026-07-29, ZERO view rows -> asserts **`pre_telemetry`** and asserts the **+1.22R is NOT scored against the
  operator's judgment** (it lands in `unattributable_r`, not `away_r` and not `decision_r`).
  **A naive "no rows -> away" implementation FAILS this test.** It is no longer carrying the discriminating
  load — T-B/T-C do that — but it is the anchor to real data RD required be kept rather than deleted.
- **T-A2 (the stability property, RULING 2's defining consequence).** Add a view row to FTRE's covered portion
  and assert it moves OFF `pre_telemetry` ONLY into an awareness-established cell — **never into
  `away_unseen`**. This is the test that pins "the classification can only move toward a POSITIVE fact"; an
  implementation that re-evaluates coverage as "now we have some rows, so treat the window as covered" flips
  FTRE to away and FAILS.
- **T-B (the SEEDED DISCRIMINATING TEST — RD ruling 3's replacement).** A seeded fire anchored 2026-08-03
  (after the epoch), cleared 2026-08-14, so its window is **FULLY covered**; ZERO view rows for it, **and view
  rows present for a SIBLING latch on those same sessions** (proving the beacon was alive) -> `away_unseen`,
  EXCLUDED from the discipline signal, R to the away bucket. This is where the acceptance SEMANTICS now live,
  and it discriminates: strip the sibling rows and the telemetry-health gate turns the same input into
  `telemetry_unhealthy`; move the anchor one session before the epoch and it becomes `pre_telemetry`.
- **T-C (the pessimistic default).** Same substrate as T-B, but with view rows for THIS latch and no intent and
  no attestation -> `discipline_lapse`. Flip a single view row from present to absent and T-C becomes T-B —
  the pair is the viewed/never-viewed discriminator the brief's single test does not contain.

#### A.1.5 THE GATE IS CLOSED — RD RULED 2026-07-28, and the losing branch is DELETED

**Codex R1 MAJOR 2 required ONE source of truth, and there now is one.** RD ruled §A.1 on 2026-07-28 in
favour of this plan's direction (with one simplification — `partial_telemetry_unresolved` collapsed into
`pre_telemetry`, §A.1.1). Accordingly:

- **The branch machinery is GONE.** `AWAY_RATE_COUNTED_DISPOSITIONS = frozenset({"away_unseen"})`, fixed.
  The alternative branch is DELETED from this plan rather than left as an option, exactly as the pre-ruling
  version of this section required of whichever branch lost.
- **Tasks 4, 5 and 9 are UNBLOCKED.** They were gate-blocked pending this ruling; nothing is gate-blocked now.
- **The ORCHESTRATOR carries the re-baseline** into `docs/prepared-order-form-21b-commissioning-brief.md` §3
  and `docs/rd-state.md` at the return, so the brief's §3 acceptance test and the shipped classifier say the
  same thing. The implementer does not edit director-owned docs.
- **`UNATTRIBUTABLE_DISPOSITIONS` is still DERIVED by set subtraction** (§F.3), not hand-written — the ruling
  fixes the away set's CONTENT, it does not remove the reason the derivation exists (an overlap between the
  two buckets must stay unrepresentable, not merely untested).

### A.1.6 THE TWO UNASSIGNED BUCKET CELLS — **RULED BY RD 2026-07-28**

Both cells had been arriving by DEFAULT through a bucket fallthrough. RD ruled each, and separately commended
the mechanism that surfaced them — *"RAISE-on-unlisted plus a test asserting every disposition appears exactly
once means this class cannot recur by omission, and that is worth more than either ruling, because the next
unlisted disposition will be one neither of us has thought of."* **That guard is kept exactly as built** (§F.3).

**RULING 1 — `pending_live`: EXCLUDED FROM EVERY RATE. Reported, never scored.**

A latch that has not terminated **is not an observation yet**: there is no outcome, the operator can still
act, and its value moves as the window runs. RD ties this directly to the FTRE retirement —
*"a verdict that can flip on behaviour AFTER the window it purports to measure is not a measurement."*

- `pending_live` is its own **reported** category, visible so the reader sees the pipeline rather than a
  silently smaller corpus.
- **EXCLUDED from every denominator** — decision, away and discipline alike.
- **Rates compute over TERMINAL, CLASSIFIABLE observations only** — and this is enforced as a GATE on
  `r_bucket_for`, NOT as one disposition among eleven (§F.3). A disposition-only encoding does not implement
  the ruling: `pending_live` is only reached for a live latch that has actionable views AND no intent, so a
  live latch carrying a `place` intent would score `accepted`, a live latch with no views would score
  `away_unseen`, and a live latch with withheld-only views would score `never_actionable` — three
  non-terminal observations in scored buckets. **Terminality gates the bucket; the disposition only names
  what was seen.**
- The ledger is self-completing: a latch leaves `pending_live` when it terminates and is classified THEN, on
  complete information. Nothing is lost by waiting; something is corrupted by not waiting.

**RULING 2 — `attested_was_away`: NEITHER existing bucket. It gets a THIRD, and the away rate is reported in
TWO forms.**

The question RD answered is whether a self-declared away is evidence *of the same kind* as a telemetry-derived
away. **It is not — therefore it does not belong in the same number** (§A.0). `decision_r` is clearly wrong,
because separating exactly this is what the away bucket is for; but merging into `away_r`
*"reintroduces, through the attestation door, the flattering path I closed at the default door"* — a
self-report about one's own diligence is systematically biased toward the more comfortable explanation, and
this is **the number that would justify automating his entries**, the one he least wants softenable.

- `attested_was_away` is a **THIRD terminal category**, reported separately.
- **EXCLUDED from the discipline signal** — if he was away it is not a judgment datum, and the attestation is
  honoured rather than second-guessed.
- The away rate is reported in **TWO FORMS over the same denominator**, so they are directly comparable:
  - **OBJECTIVE away rate** — `away_unseen` only, telemetry-derived.
  - **ATTESTED away rate** — `away_unseen` + `attested_was_away`.
- **Stage-3 auto-place reads the OBJECTIVE rate as PRIMARY, with the attested rate as an explicit UPPER
  BOUND.** The report labels them that way, so the decision cannot quietly be taken on the larger number.

**The bias guard is deliberately ONE-SIDED, and a symmetric one must NOT be added.** RD's note: attesting
*"I saw it and chose not to act"* when actually away is self-flagellating, unlikely, and **conservative** if it
happens — it moves a fire INTO the discipline signal against himself. Only the flattering direction needed a
guard.

### A.2 Which price feeds `compute_shares` — the PIVOT or the LIMIT CAP? (RD RULING REQUESTED)

The framework's order has a limit at the zone cap (`pivot * 1.03`), so the worst fill it can produce is the
cap. But the shipped `swing/recommendations/build.py:47` sizes the nightly `today_decision` off the **pivot**.
On FTRE's live numbers (pivot 18.34, stop 14.88, sizing equity 7500, `max_risk_pct` 0.005 -> $37.50):

| basis | risk/share | shares | risk if filled at the CAP |
|---|---|---|---|
| pivot 18.34 | 3.46 | **10** | 10 x 4.0102 = **$40.10 = 0.535% of equity — OVER the 0.5% policy cap** |
| zone cap 18.89 (cent-quantized, §D.1) | 4.01 | **9** | 9 x 4.01 = $36.09 = 0.481% — within the cap in every fill outcome |

**This plan recommends the LIMIT PRICE as the basis in BOTH regimes** (in the pullback regime it is the only
price the order can fill at; in the breakout regime it is the worst case), because a sizing that can breach the
risk policy on an ordinary fill is not a mandate the operator should be shown as correct. **Flagged, not
fixed:** this makes the latch's qty differ by one share from the same fire's persisted
`daily_recommendations.shares` (FTRE row id 142 says 10). The plan does NOT change
`build_recommendations` — that is a measurement-chain edit outside this arc. Instead the form renders BOTH the
basis and the divergence explicitly (§D.3), so the operator sees why the two surfaces disagree rather than
discovering it at the broker. If RD prefers pivot-parity, one constant flips and the divergence note is
deleted.

### A.3 The per-field delta is COMPUTED, not stored (RD RULING REQUESTED)

B3 calls the per-field delta "the metric". This plan stores **both sides verbatim** (the framework's order and
the operator's actual params) and computes the delta with a pure function at read time. Reasons: a stored delta
is a denormalisation that can disagree with its own inputs; the delta's DEFINITION will improve (fill quality
arrives in stage 3) and a stored copy freezes V1's definition into history; and B3's own "recomputable later"
language points the same way. The delta is still first-class — it is `OrderDelta`, it has its own tests, and it
is what the CLI report prints. **What is NOT recomputed is the framework side**: that is stored verbatim
precisely so a future code change cannot rewrite what the operator was shown.

### A.4 Store what can DRIFT; reference what cannot (the minimality principle for §C.2)

`latched_pivot` and `latched_initial_stop` are NOT stored on the ledger row: they are pinned exactly by
`candidate_id NOT NULL ... ON DELETE RESTRICT`, and `candidates` is append-only in production (zero
`UPDATE`/`DELETE` statements anywhere in `swing/`, `research/`, `scripts/` — re-verified at this writing).
Everything config- or policy-derived IS stored (`zone_cap_pct`, sizing equity, `max_risk_pct`,
`position_pct_cap`, the `risk_policy_id`, the sizing basis, the regime close and the session that close is
DATED), because every one of those can move and a moved value silently rewrites history. This is the cut that
keeps the table minimal without losing anything unrecoverable.

**THE CUT IS DRAWN AT WHAT THE CARD SHOWS, NOT AT WHAT THE SIZING FORMULA CONSUMES (Codex R27 MAJOR).** The
first pass applied the rule to the sizing INPUTS and stopped, leaving the card-rendered values
`real_equity`, `equity_floor` and `nightly_recommendation_shares` un-anchored and unstored. All three can DRIFT, so §A.4's own rule already covered them — it simply had
not been applied to them. And the omission is not cosmetic: if `real_equity` moves while the floor still
binds, `sizing_equity` is UNCHANGED, so the anchor digest is unchanged, the stale-form comparison passes, and
the row records a derivation whose printed line — *"sizing equity $7,500.00 = max(real equity $1,2xx.xx,
risk_equity_floor $7,500.00)"* — the operator demonstrably did not see. That falsifies this plan's central
claim in the one place it is most load-bearing.

So the rule is restated to close the CLASS rather than to patch three fields:

> **EVERY value the card presents INSIDE the prepared-order derivation block is hidden-anchored, compared at
> POST, and stored. Anything not anchored MUST NOT be rendered inside that block.** The two are one decision:
> a number is either part of the audited derivation, or it is not shown as part of it.

The three added columns are `derivation_real_equity`, `derivation_equity_floor` and
`derivation_nightly_recommendation_shares`, each carried in `anchor_digest` and in the §G.2 field-by-field
comparison. **EXACTLY TWO derivation columns are legitimately NULLABLE on a `place`/`decline` row, and §C.2
names both with their reason (Codex R28 MAJOR):** the nightly count (no `daily_recommendations` row exists
for that fire) and `derivation_risk_policy_id` (the sizing RATE comes from `cfg.risk.max_risk_pct`, NOT from
the policy row — §D.2 — so a missing active policy does NOT withhold the form; the id is provenance, and the
card renders an explicit *"no active risk_policy row"* line rather than a blank, because an unlabelled gap is
the quiet reduction §A.1.1 forbids). Every other derivation column is NOT NULL on those kinds.
**The other rendered values are DERIVED, not independent, and are deliberately NOT stored:**
`risk_per_share`, `max_risk_dollars`, `shares_by_risk`, `shares_by_position_cap` and `binding_constraint` are
pure functions of values that ARE stored plus `latched_initial_stop` (pinned by `candidate_id`), so storing
them would be the denormalisation §A.3 rejects. The test that pins the distinction: recomputing all five from
the stored row must reproduce the rendered card exactly — if any one cannot be recomputed, it belongs in the
stored set and the rule above says so.

**A test mutates ONLY `real_equity` between render and POST, with the floor still binding, and asserts a
first-write `409`** — under the pre-fix column set that POST succeeds, so the cell discriminates.

---

## B. The 21-G coupling (BINDING — 21-G merges before this arc's ledger goes live)

**Why the order binds:** the regime selection determines the recorded order TYPE. A stale-price regime writes a
WRONG TYPE into the parity ledger, so a framework-vs-actual "mismatch" at RD's monthly read would be the
framework's own defect masquerading as an operator divergence — unattributable after the fact. (20-A's
Half-A-before-Half-B: fix the writer before you trust what it writes.)

**How this plan is built so it cannot assume pre-21-G behaviour:**

1. **The regime is consumed through the EXISTING seam and never re-implemented.**
   `swing/latches/orders.py:expected_mandate_order_type(latched_pivot=..., last_close=...)` is the ONLY source
   of the mandate form in this arc. Whatever 21-G does to make the close sound flows through automatically.
   A test pins that `swing/latches/order_intent.py` contains no independent pivot-vs-close comparison.
2. **`expected_mandate_order_type(...) is None` is a FIRST-CLASS state, not an edge case.**
   When the regime is undeterminable the prepared-order form is **WITHHELD** — the panel renders the mandate
   facts and the reason, and offers no ACCEPT button. A form that guessed the type would write the wrong type
   into the ledger. This is the asymmetry rule again: from a stale close you may raise a mismatch alarm, but
   you may not assert a match — and a prepared order IS an assertion.
3. **The withheld state is the CURRENT live state, verified.** Today the derivation session is 2026-07-28 and
   FTRE's newest close is dated 2026-07-27, so the regime is undeterminable and the form is withheld on the
   live substrate right now. The plan is therefore built against the withheld path as the DEFAULT, not the
   exception, and the GUI witness (§L) explicitly witnesses BOTH the withheld and the offered state.
4. **The regime provenance is recorded on every intent row**: `derivation_regime_close` plus
   `derivation_regime_close_session`. If 21-G later changes what counts as a usable regime price, RD can tell
   from the ledger alone which rows were written under which rule. Cheap now, unrecoverable later.
5. **File-disjointness holds.** This arc touches no file 21-G is expected to touch
   (`swing/evaluation/orchestration.py`, `swing/evaluation/evaluator.py`, and the read-side shape check).
   The one shared file is `swing/latches/orders.py`, which this arc only READS from.

---

## C. Schema — migration `0033`, v32 -> v33 (B7)

### C.1 The `latch_view_events` rebuild: the `surface` column (B4)

CHARC deliberately deferred `surface` off `0032` so it lands with a real consumer. B4's requirement is
`(surface, latch_ids_rendered_with_actionable_detail, timestamp)`.

**The "with actionable detail" half IS A COLUMN — a contract alone is not enough, and the plan's first draft
was wrong about this (Codex R7 CRITICAL).** The draft said a view row exists iff the mandate was rendered
actionably, and then left the beacon emitting every live `candidate_id`. On the CURRENT live substrate every
prepared-order form is WITHHELD (§B.3, regime undeterminable), so **every one of those withheld renders would
have been recorded as a full "he saw the mandate" view** — and the away/lapse split would be computed from
renders that never presented a decision. It is not even a bias in one direction: it inflates
`discipline_lapse`, deflates `away_unseen`, and therefore DEFLATES the away rate, arguing against stage-3
auto-place on evidence the panel never actually showed him.

Nor can the fix be "just do not record a withheld render", which was the draft's implicit position: then a
latch whose form was withheld for its whole armed window — the permanently-inert case §H's `permanent` branch
already describes — would classify `away_unseen` even though the operator checked the panel diligently every
day. That inflates the away rate instead. **Both silences are wrong, and they are wrong in opposite
directions, which is the tell that the fact needs to be RECORDED rather than inferred.** So:

```sql
actionable_at_first_view INTEGER NOT NULL CHECK (actionable_at_first_view IN (0, 1)),
actionable_at_last_view  INTEGER NOT NULL CHECK (actionable_at_last_view  IN (0, 1)),
actionable_ever_viewed   INTEGER NOT NULL CHECK (actionable_ever_viewed   IN (0, 1)),
```

- `1` — the latch's mandate was rendered in a form sufficient to act on (the prepared-order form was OFFERED).
- `0` — the latch's card rendered, but its prepared order was WITHHELD, so no decision was presented.

**THREE columns, and each answers a DIFFERENT question.** A single `actionable` advanced by
`MAX(existing, new)` would let an 18:00 offered render retroactively upgrade an 09:00 withheld one — while the
row still carries `first_viewed_ts = 09:00`, so the record would assert "first viewed at 09:00, with an
actionable mandate", which is false. But naming the MAX column `..._at_last_view` commits the mirror-image
lie: after an offered 09:00 render and a withheld 18:00 one, `last_viewed_ts` advances to 18:00 while the
column still says the last view was actionable. Both are the stored fact depending on a LATER reload. So the
first/last pair mirror the idiom `0032` already uses for `latch_state_at_first_view` /
`latch_state_at_last_view` and stay literally true of their OWN view, and the monotone fact gets its own
honestly-named column:

| column | write rule | means |
|---|---|---|
| `actionable_at_first_view` | set at INSERT, **NEVER rewritten** | what the FIRST view of this session showed |
| `actionable_at_last_view` | overwritten with the NEW value on every UPDATE | what the LATEST view showed |
| `actionable_ever_viewed` | `MAX(existing, new)` — monotonic `0 -> 1`, never back | was the mandate offered AT ANY POINT this session |

**Classification reads `actionable_ever_viewed = 1`** as "the mandate WAS actionably presented in this
session" (§E.3) — the honestly-named column for that question, and the ONLY actionability column any
classification, health or bucket rule may read. The `..._at_first_view` / `..._at_last_view` pair are audit
companions to their own timestamps and are never a classifier input.

Consumers, each distinct (§E.3, §F.1):
- the away/lapse split counts **only rows with `actionable_ever_viewed = 1`** as a view;
- a latch with only `actionable_ever_viewed = 0` rows across its whole armed window classifies
  **`never_actionable`** — a new disposition, EXCLUDED from the discipline signal and from the away rate for
  the same reason `pre_telemetry` is: the instrument never presented a decision, so there is nothing to score;
- telemetry health counts **either kind** toward `covered_sessions` — a row of either kind proves the beacon
  fired, which is all that check is asking.

A count-only tile (21-F resolution (c)) still records NOTHING at all — it renders no card.

**The grain must become per-(latch, session, SURFACE)**, or 21-F cannot record a dashboard view in a session
the panel was also opened — and "analyse the two surfaces separately" (21-F §4 resolution (b)) becomes
impossible. SQLite cannot drop a table-level `UNIQUE`, so this is a rebuild:

```sql
CREATE TABLE latch_view_events_new (
    view_event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id       INTEGER NOT NULL REFERENCES candidates(id) ON DELETE RESTRICT,
    evaluation_run_id  INTEGER NOT NULL,
    ticker             TEXT NOT NULL,
    detection_date     TEXT NOT NULL,
    pipeline_run_id    INTEGER REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    surface            TEXT NOT NULL,          -- NEW (B4)
    view_session_date         TEXT NOT NULL,
    first_viewed_ts           TEXT NOT NULL,
    last_viewed_ts            TEXT NOT NULL,
    view_count                INTEGER NOT NULL,
    latch_state_at_first_view TEXT NOT NULL,
    latch_state_at_last_view  TEXT NOT NULL,
    -- THREE FACTS, NAMED HONESTLY (R24 MAJOR). The draft advanced
    -- `actionable_at_last_view` with MAX(), which makes it mean "EVER actionable
    -- this session" while its NAME promises "actionable at the last view" -- so
    -- a withheld render AFTER an offered one left the row asserting the last
    -- view was actionable when it was not, beside a `last_viewed_ts` that HAD
    -- advanced. The classifier's real question is "was it ever offered this
    -- session", so that fact gets its own honestly-named column and the
    -- first/last pair stay literally true of their own views.
    actionable_at_first_view  INTEGER NOT NULL,   -- immutable after insert
    actionable_at_last_view   INTEGER NOT NULL,   -- the LAST view's own value
    actionable_ever_viewed    INTEGER NOT NULL,   -- MAX(), monotonic 0 -> 1
    CHECK (surface IN ('latch_panel')),        -- widened by the surface that adds itself
    CHECK (actionable_at_first_view IN (0, 1)),
    CHECK (actionable_at_last_view  IN (0, 1)),
    CHECK (actionable_ever_viewed   IN (0, 1)),
    CHECK (actionable_ever_viewed >= actionable_at_first_view),
    CHECK (actionable_ever_viewed >= actionable_at_last_view),
    -- THE MONOTONIC CONTRACT, ENFORCED IN SQL AND NOT ONLY IN PYTHON (Codex
    -- R17). The prose claimed this was mirrored; the DDL only bounded each
    -- value, so a raw INSERT could store a row the dataclass REJECTS -- the DB
    -- holding a shape the read path cannot hydrate, which is the dangerous
    -- asymmetry direction the #11 discipline exists to stop. The contract runs
    -- `ever >= first` and `ever >= last` ONLY. `first=1, last=0` is DELIBERATELY
    -- LEGAL: it is the true record of an offered 09:00 render followed by a
    -- withheld 18:00 one, and forbidding it would reimpose the "last means ever"
    -- lie the third column was added to end. The R17-era pairing of first
    -- against last is therefore NOT reproduced here.

    -- Every 0032 CHECK reproduced -- WITH the section C.1.1 date-CHECK
    -- CORRECTION applied to both date columns. This is a NAMED, DELIBERATE fix
    -- riding the rebuild, not a by-product of it; see C.1.1 for the reasoning
    -- and the two INDEPENDENT tests it requires.
    -- THE THREE-PREDICATE DATE GUARD (C.1.1). Used VERBATIM at every date
    -- column in this arc; if a fourth malformed shape is ever found, it is
    -- added HERE and propagated, never patched at one site.
    CHECK (COALESCE(length(detection_date) = 10
           AND date(detection_date) IS NOT NULL
           AND date(detection_date) = detection_date
           AND CAST(substr(detection_date, 1, 4) AS INTEGER) BETWEEN 1 AND 9999, 0)),
    CHECK (COALESCE(length(view_session_date) = 10
           AND date(view_session_date) IS NOT NULL
           AND date(view_session_date) = view_session_date
           AND CAST(substr(view_session_date, 1, 4) AS INTEGER) BETWEEN 1 AND 9999, 0)),
    -- >>> THE REMAINING 0032 CHECKS ARE REPRODUCED HERE. This is a PLACEHOLDER
    -- >>> in the plan and MUST NOT be copied as-is (Codex R28 MAJOR: copied
    -- >>> literally, this migration does not run). See "THE REBUILD IS
    -- >>> MECHANICAL" below for the source-of-truth procedure and the three
    -- >>> tests that make a hand-reconstruction detectable.
    -- The grain stays (latch, session, surface). Actionability is an ATTRIBUTE
    -- of that row, not part of its key: within one session a card can flip
    -- between withheld and offered as the nightly lands or the regime goes
    -- stale, and the three columns record that flip WITHOUT splitting the row
    -- (first is frozen, last tracks the newest view, ever is the monotone OR).
    -- KEYED ON `candidate_id` -- the declared IMMUTABLE BRIDGE KEY -- not on
    -- (evaluation_run_id, ticker) (Codex R15 MAJOR 2). Those two are equivalent
    -- today (`candidates` is UNIQUE on (evaluation_run_id, ticker), and the
    -- identity-coherence trigger binds all three together), so this is NOT a
    -- live aliasing bug -- it is an architectural one: a plan that declares
    -- candidate_id the bridge key and then keys its telemetry on a different
    -- tuple has two keys for one identity, and the argument about whether they
    -- can diverge should not need to be had at all. One column, exact, and free
    -- here because the table is being rebuilt anyway.
    UNIQUE (candidate_id, view_session_date, surface)   -- widened + re-keyed
);
-- THE COLUMN LIST IS WRITTEN OUT EXPLICITLY, never left positional. A bare
-- `INSERT INTO t SELECT ...` binds by POSITION, so the moment a column is added
-- to the DDL and not to the SELECT the migration fails at apply time (or, worse
-- on a differently-ordered rebuild, silently lands values in the wrong columns).
-- That is not hypothetical here: the THIRD actionability column was added to the
-- DDL one round before this list, and the positional form was left at two values.
INSERT INTO latch_view_events_new (
    view_event_id, candidate_id, evaluation_run_id, ticker, detection_date,
    pipeline_run_id, surface, view_session_date, first_viewed_ts, last_viewed_ts,
    view_count, latch_state_at_first_view, latch_state_at_last_view,
    actionable_at_first_view, actionable_at_last_view, actionable_ever_viewed)
    SELECT view_event_id, candidate_id, evaluation_run_id, ticker, detection_date,
           pipeline_run_id, 'latch_panel', view_session_date, first_viewed_ts,
           last_viewed_ts, view_count, latch_state_at_first_view, latch_state_at_last_view,
           0, 0, 0         -- see "the legacy backfill is 0, not 1" below
    FROM latch_view_events;
DROP TABLE latch_view_events;
ALTER TABLE latch_view_events_new RENAME TO latch_view_events;
-- >>> the three 0032 indexes + BOTH 0032 identity-coherence triggers are
-- >>> RECREATED here, VERBATIM apart from the table name. Also a placeholder.
```

**THE REBUILD IS MECHANICAL, AND THE PLAN IS NOT ITS SOURCE OF TRUTH (Codex R28 MAJOR).** The SQL above is an
ILLUSTRATION carrying two literal placeholders; copied as-is the migration does not run, and — worse — an
instruction to "reproduce `0032` verbatim except one change" hands the single most regression-prone step in
the arc to reconstruction from memory. Inlining the full DDL here would not fix that: it would create a
SECOND copy of `0032` that can itself be mistyped, and the implementer would diff against the plan instead of
against the shipped table. So the procedure is:

1. **READ the shipped DDL, do not retype it** — `swing/data/migrations/0032_latch_view_telemetry.sql` is the
   source of truth for the CHECKs, the indexes and both triggers.
2. **Apply EXACTLY these FIVE deltas, which are a CLOSED LIST:**
   (a) `+ surface TEXT NOT NULL` with `CHECK (surface IN ('latch_panel'))`;
   (b) `+` the three actionability columns with their `IN (0,1)` and two `ever >=` CHECKs;
   (c) the §C.1.1 three-predicate strengthening on `detection_date` and `view_session_date` — **the ONLY
       change to an existing CHECK**;
   (d) `UNIQUE (evaluation_run_id, ticker, view_session_date)` -> `UNIQUE (candidate_id, view_session_date,
       surface)`;
   (e) `+` the ISO-seconds SHAPE guards on `first_viewed_ts` and `last_viewed_ts` (§C.1.1), with the existing
       `last_viewed_ts >= first_viewed_ts` ordering CHECK PRESERVED alongside them.
   Anything else differing between the two DDLs is a mistake, not a decision.
3. **Three tests make a hand-reconstruction detectable, and they are not substitutes for each other:**
   - **`executescript` on a REAL v32 DB** — the migration applies without error. Catches syntax, unbalanced
     parens and unresolvable references, which is the class a prose review cannot see.
   - **The §C.1 0032-preservation suite** — every shape `tests/data/test_migration_0032.py` proves the old
     table rejects, the new table still rejects. Catches a DROPPED constraint.
   - **A CHECK-SET DIFF, parsed from both DDLs, AT EXPRESSION GRANULARITY** — normalise whitespace and
     compare the set of CHECK EXPRESSIONS on the pre-`0033` table against the post-`0033` table. Catches an
     ADDED or SILENTLY-ALTERED constraint, which neither of the other two can: the preservation suite only
     re-runs known rejections, and `executescript` is happy with a constraint nobody intended.
     **THE ORACLE IS DERIVED FROM THE DELTA LIST, NOT RESTATED BESIDE IT (Codex R29 MAJOR; generalised in
     the post-R29 editorial pass).** "The symmetric difference equals the four deltas" was not a well-defined
     assertion — the deltas are at FEATURE granularity and one of them (the re-keyed `UNIQUE`) is not a
     CHECK at all, so an implementer had to invent grouping rules. And restating the diff as its own
     hand-kept list with cardinalities would just create a SECOND roster to drift against the first, which is
     the generator this plan is retiring. So the test COMPUTES its expectation:

     ```
     expected_removed = the CHECK expressions delta (c) supersedes
     expected_added   = the CHECK expressions deltas (a), (b), (c) and (e) introduce
     expected_same    = parse(0032) - expected_removed
     assert parse(0033) - parse(0032) == expected_added
     assert parse(0032) - parse(0033) == expected_removed
     ```

     Deltas (a), (b), (c) and (e) are the CHECK-bearing ones; **delta (d) is a `UNIQUE` and contributes
     NOTHING to a CHECK diff** — it, the three indexes and both triggers are asserted by their own
     introspection tests. No cardinality appears in the assertion or in this bullet: add a CHECK to a delta
     and the oracle follows it automatically, which is exactly what a hand-kept "ADDED (10)" could not do.
     The `UNIQUE` re-key, the three indexes and both triggers are asserted SEPARATELY, by their own
     introspection tests — a CHECK diff cannot speak about them.
   The trigger bodies get the same treatment — compare the post-`0033` `sqlite_master` trigger SQL against
   `0032`'s, modulo the table name, and assert equality rather than merely that the triggers fire.

**THE REPO NATURAL KEY MOVES WITH THE CONSTRAINT (Codex R3 MAJOR 2).** A widened `UNIQUE` is cosmetic if the
repo still looks up on the old triple — the second surface's `record_view` would find the panel's row and
UPDATE it, so two surfaces would silently share one row and one `view_count`. So `surface` becomes part of the
natural key EVERYWHERE in `swing/data/repos/latch_view_events.py`:

**THE BEACON PAYLOAD AND HANDLER MOVE WITH IT.** `LatchPanelVM.beacon_payload_json` splits the single
`candidate_ids` field into `actionable_candidate_ids` and `withheld_candidate_ids`.

**The RENDER-TIME claim is the datum, and the POST-time re-derivation does NOT override it (Codex R11 MAJOR
3).** The draft recorded "the weaker claim" on disagreement, which sounds conservative and is actually a
corruption: `actionable` is a fact about *what the operator was shown*, and a card that WAS offered when he
looked does not stop having been offered because the latch changed a moment later. Downgrading it to `0`
would manufacture a `never_actionable` for a mandate he was genuinely presented with. So:

- **`actionable` is taken from the PAYLOAD** — which set the id was posted in.
- **The re-derivation still gates EXISTENCE, exactly as 21-A already does:** only ids in the anchor-session
  LIVE set are recorded at all (the intersection rule). A forged id writes nothing.
- **A render-vs-re-derivation disagreement is LOGGED as a warning, not silently applied.** It is the signal
  that the two computations diverged; it is not evidence about what he saw.
- This is not a retreat from validate-do-not-trust. The intent handler still refuses a mutated framework
  anchor outright (§G.2), because THERE the payload asserts a computation the server owns. Here the payload
  reports a RENDER — something only the render can know — so the server's job is bounding it (live set,
  session anchor, id shape), not recomputing it.

- `get_view(conn, *, candidate_id, view_session_date, surface)` — keyed on the BRIDGE KEY (§C.1), with
  `surface` REQUIRED and NO default (a default would re-create the bug the first time a caller forgets it —
  the default-arg-filter gotcha).
- `record_view(..., surface=..., actionable=...)` — the SELECT-then-UPDATE-or-INSERT keys on the FOUR-tuple.
  On INSERT all THREE actionability columns take the passed value. On UPDATE, exactly the §C.1 table:
  `actionable_at_first_view` is **NEVER rewritten**, `actionable_at_last_view` is **OVERWRITTEN with the new
  value** (it describes the latest view and must be able to fall `1 -> 0`), and `actionable_ever_viewed`
  becomes `MAX(existing, new)` (monotonic `0 -> 1`, never back) — alongside the existing monotonic
  `view_count` / `last_viewed_ts` advance.
- `list_views_for_latch(conn, *, candidate_id, surfaces=None)` /
  `list_views_for_session(conn, *, view_session_date, surfaces=None)` — `None` means ALL
  surfaces (a raw read); every CLASSIFICATION caller passes `surfaces=ACTIONABLE_VIEW_SURFACES` explicitly
  (§E.3), so no reader silently inherits a set it did not choose.
- `_row_to_model`, `_COLS` and **`swing/data/models.py:LatchViewEvent`** carry `surface` and **ALL THREE**
  actionability columns — `actionable_at_first_view`, `actionable_at_last_view` AND
  `actionable_ever_viewed`. The model was a plain omission in the first draft (Codex R15 MAJOR 1), which would
  have left `never_actionable`, `covered_sessions` and the beacon split with no hydrated fields to read; the
  `ever` column is the one CLASSIFICATION actually reads (§C.1), so omitting it would reproduce that defect
  exactly. `__post_init__` validates all three against `{0, 1}` (the `Literal` hint is not runtime-enforced)
  and rejects `actionable_ever_viewed < actionable_at_first_view` and
  `actionable_ever_viewed < actionable_at_last_view` — the two monotonic contracts, mirrored from the SQL side
  under the #11 discipline. It does **NOT** constrain `actionable_at_last_view` against
  `actionable_at_first_view`: a `1 -> 0` fall between them is the CORRECT record of an offered render followed
  by a withheld one, and a validator forbidding it would re-impose the very "last means ever" lie the third
  column exists to end.

Tests (Task 1): a replay on the SAME surface -> ONE row, `view_count=2`; `get_view` without `surface` raises
`TypeError`; the UNIQUE's `surface` leg proved by DDL introspection. NO two-surface INSERT test (R18 MAJOR 4).


**THE LEGACY BACKFILL IS `0`, NOT `1` (Codex R16 MAJOR 2).** The first draft copied historical rows with both
actionability columns `= 1`, which INVENTS a fact: the old schema recorded no actionability at all, so
asserting those views were actionable is manufacturing evidence, in the flattering-to-the-instrument
direction. `0` asserts strictly less — *no actionable presentation is RECORDED for this row* — which is
literally true of a row written by a schema that recorded no such thing. A Task-1 test FAILS a backfill of
`1`. **On production this is moot and that is VERIFIED, not assumed:** `latch_view_events` holds ZERO rows on
the live DB (2026-07-28), so the copy moves nothing; the `0` exists for a dev/test DB whose six-day-old
telemetry has no downstream consumer.

**Rebuild risk is bounded and stated:** the live table holds ZERO rows, so the copy is a no-op in production —
but the copy is written anyway so a non-empty dev/test DB migrates correctly. **The two identity-coherence
triggers and **every CHECK `0032` declares — PARSED FROM THE FILE, NEVER COUNTED IN PROSE** (this plan
carried "seven" for several rounds; the real figure is eight, and a cardinality nobody can verify from the
artifact itself is precisely what the §C.1 CHECK-diff oracle replaces with a parse) MUST be reproduced with EXACTLY ONE intended change — the §C.1.1
date-CHECK correction on `detection_date` and `view_session_date`. Everything else is byte-for-byte**; a test
asserts the post-`0033` table still rejects each of the shapes `tests/data/test_migration_0032.py` proves it
rejects, AND additionally rejects the two shapes C.1.1 names (this is the single largest regression risk in
the arc and it gets its own task step). "Byte-for-byte except one named change" is the only honest form of
that instruction: an unqualified byte-for-byte would tell an implementer to reproduce the defect.

**The cheaper alternative CHARC may prefer, named for a veto:** `ALTER TABLE ... ADD COLUMN
first_view_surface / last_view_surface` (no rebuild, grain unchanged). It is smaller, and it LOSES per-surface
counts — you could not tell five panel opens from one dashboard glance. The plan recommends the rebuild
because B4's stated purpose is keeping 21-F's surface architecture unconstrained, and the cheaper option
constrains it.

### C.1.1 THE `0032` DATE-CHECK DEFECT — a NAMED fix riding the rebuild (RD ruled `20260729T085410Z`)

**A SQLite `CHECK` PASSES WHEN ITS EXPRESSION EVALUATES TO NULL, and `date('2026-99-99')` IS NULL.** So
`date(x) = x` evaluates to `NULL = '2026-99-99'` -> NULL -> the CHECK passes. Reproduced empirically at this
writing, twice, on an in-memory DB:

| value | `length=10 AND date(x)=x` | `length=10 AND date(x) IS NOT NULL` | both halves |
|---|---|---|---|
| `'2026-99-99'` | **ACCEPTED** | rejected | rejected |
| `'garbage123'` | **ACCEPTED** | rejected | rejected |
| `'2026-02-30'` | rejected (normalises to `2026-03-02`, so `!= x`) | **ACCEPTED** | rejected |
| `'2026-07-29'` | accepted | accepted | accepted |

**BOTH HALVES ARE REQUIRED AND NEITHER IS SUFFICIENT.** Round-trip equality catches the NORMALISING case;
`IS NOT NULL` catches the INVALID case. The middle column is the reason this is not a "just add IS NOT NULL"
edit and the left column is the reason it is not a "the existing check is fine" one.

**THE SCOPE IS EVERY DATE *AND EVERY TIMESTAMP*, INCLUDING THE TWO THIS SECTION ORIGINALLY MISSED (Codex R29
MAJOR).** The section claimed "every date and timestamp CHECK" while the rebuilt `latch_view_events` kept
`first_viewed_ts` / `last_viewed_ts` guarded ONLY by `last_viewed_ts >= first_viewed_ts` — an ORDERING
constraint, not a SHAPE one — and the dataclass only string-compares them. A raw append could store a
malformed or absurd view timestamp that hydrates fine and renders as authoritative telemetry, which is B4's
own recorded fact. So the rebuild ALSO applies the full ISO-seconds guard (the `recorded_ts` form: length,
GLOB shape, the date half's three predicates, and hour/minute/second ranges) to BOTH columns, mirrored in
`LatchViewEvent.__post_init__`, with their own raw-insert rejection tests. **This is a fifth delta to the
rebuild** and §C.1's delta list and CHECK-diff oracle count it: `+2` strengthened timestamp CHECKs, and the
`last_viewed_ts >= first_viewed_ts` CHECK is PRESERVED unchanged beside them (it answers a different
question, and the ordering guarantee is not implied by either shape guard).

**AND A THIRD PREDICATE — THE YEAR RANGE (Codex R26 MAJOR).** Both halves together still ACCEPT
`'0000-01-01'`: SQLite's `date()` round-trips year zero happily, while Python's `date.fromisoformat` raises
*"year must be in 1..9999, not 0"* — verified both ways at this writing. That is precisely the asymmetry
direction the #11 discipline exists to stop: **the DB holding a row the read path cannot hydrate.** The
production writer cannot emit it (`datetime.now()` has no year zero), so this is the raw-append vector only —
but so is everything else this section guards, and a mirror that is right for two malformed shapes and wrong
for a third is not a mirror. Every date and timestamp CHECK therefore also carries
`CAST(substr(x, 1, 4) AS INTEGER) BETWEEN 1 AND 9999`, mirrored in the dataclass validators (where
`fromisoformat` already enforces it), with `'0000-01-01'` / `'0000-01-01T00:00:00'` as their own rejection
cases. Verified: with the year predicate, `0000-01-01` rejects while `0001-01-01` and `9999-12-31` still
pass, so the guard is not merely narrowing the useful range.

**This is LIVE on the production database.** Migration `0032`'s `latch_view_events` writes the weak form on
`detection_date` and `view_session_date` — and those are the **only two occurrences of the pattern in the
entire `swing/data/migrations/` tree** (verified by grep at this writing; no other migration writes a
`date(x) = x` CHECK). 21-B already REBUILDS that table, so the correction rides the rebuild at zero extra
migration cost and zero extra risk.

**Worth recording because it is the interesting part:** `0032`'s own comment argues *for* round-trip equality
and *against* `IS NOT NULL`, and reasons correctly about normalisation the whole way — it simply concluded
that normalisation was the entire failure space. An author reasoning carefully to the wrong conclusion is a
harder defect to catch than an author not reasoning at all, which is exactly why the fix is pinned by tests
rather than by a corrected comment.

**RD's conditions, binding on this plan:**

1. **DELIBERATE, NOT INCIDENTAL.** This section exists so the fix is a named change with its reasoning on the
   record, rather than a silent by-product of a rebuild done for another purpose. The migration comment points
   here; the task step names it.
2. **BOTH HALVES TEST-PINNED INDEPENDENTLY (Task 1).** TWO separate tests per date column, never one combined:
   - **the NORMALISING case** — `'2026-02-30'` is REJECTED. Passes with round-trip equality alone; FAILS
     against an `IS NOT NULL`-only guard.
   - **the INVALID case** — `'2026-99-99'` is REJECTED. Passes with `IS NOT NULL` alone; FAILS against the
     shipped round-trip-only guard.
   A single test asserting "a malformed date is rejected" would go green with HALF the guard missing,
   whichever half was dropped — which is the whole reason RD required them split.
3. **STANDING CONDITION.** If any NEW `latch_view_events` writer lands before 21-B merges, **the CHECK fix
   lands FIRST**, on its own, ahead of that writer. The exposure is theoretical only while the write path
   stays closed (below); a new writer is exactly what could open it.

**Do NOT overstate this, and the plan is explicit about the limit.** The input space is closed TODAY — but by
the WRITE PATH, not by provenance and not by the CHECK:

- `view_session_date` reaches the writer as `anchor.isoformat()` where `anchor = date.fromisoformat(raw)` at
  the route boundary (`swing/web/routes/latches.py:_parse_beacon_anchor`) — a **parse-and-reserialise**, so a
  malformed posted value raises before it can reach SQL.
- `detection_date` arrives on a `LatchIdentity`, whose `__post_init__` runs `parse_session_date` (
  `date.fromisoformat`) — a **validating constructor**, which rejects both `'2026-99-99'` and `'2026-02-30'`.

So this is **defence in depth on a currently-closed input space, not an active corruption**, and no claim is
made that bad rows exist. What the CHECK buys is that the closure stops depending on two callers continuing
to do the right thing — which is the same argument the immutability trigger makes in §C.2, and the same one
`0032`'s identity-coherence trigger already makes for a writer that "cannot produce that shape".

**Out of scope, flagged not fixed:** whether the SAME class exists in any OTHER shipped table's date or
timestamp CHECKs is a `swing/data/migrations/` audit the ORCHESTRATOR owns, not this arc. The grep above
bounds it for the `date(x) = x` pattern specifically; it does not bound near-miss variants.

### C.2 The new table: `latch_order_intents`

APPEND-ONLY (the `reconciliation_corrections` precedent). One row per operator DECISION. The classification
and the delta are READS over these rows, never stored state.

```sql
CREATE TABLE latch_order_intents (
    intent_id            INTEGER PRIMARY KEY AUTOINCREMENT,

    -- ===== LATCH IDENTITY BLOCK -- columns 2-6, VERBATIM per
    -- swing/latches/identity.py:LATCH_IDENTITY_COLUMNS (RD finding 4: BOTH id
    -- spaces). candidate_id is the IMMUTABLE BRIDGE KEY this ledger joins to
    -- latch_view_events on: ON a.candidate_id = b.candidate_id. NOT NULL +
    -- RESTRICT so a future pruner fails loudly instead of silently severing it.
    candidate_id         INTEGER NOT NULL REFERENCES candidates(id) ON DELETE RESTRICT,
    evaluation_run_id    INTEGER NOT NULL,
    ticker               TEXT NOT NULL,
    detection_date       TEXT NOT NULL,
    -- NO FK, DELIBERATELY (Codex R16 CRITICAL, re-raised at R17 because the
    -- first fix attempt never landed). R13 wrote the RULE -- "every FK here is
    -- RESTRICT; no SET NULL appears in this DDL" -- and this line contradicted
    -- it for four rounds: a SET NULL cascade is an UPDATE, and trg_loi_no_update
    -- aborts it.
    --
    -- The resolution is NOT to flip it to RESTRICT: `pipeline_runs` IS genuinely
    -- pruned in this project, and an immutable ledger row holding RESTRICT would
    -- block that pruning forever. But SET NULL is WORSE than either, because it
    -- would DESTROY the detection identity RD's finding 4 asked to be stored
    -- ("cheap now, unrecoverable later") on the very event the ledger exists to
    -- remember. So `pipeline_run_id` is a PLAIN INTEGER here -- a denormalised
    -- copy exactly like evaluation_run_id / ticker / detection_date beside it --
    -- VALIDATED AT INSERT by the identity-coherence trigger (while the referent
    -- still exists) and then PRESERVED FOREVER. Validate at write; keep the fact
    -- after the referent is gone. That is what an audit ledger is for.
    --
    -- Deliberately DIVERGENT from `latch_view_events`, which keeps its 0032
    -- SET NULL: that table is not UPDATE-forbidden, so the cascade works there,
    -- and 21-A's shipped behaviour is not this arc's to change.
    pipeline_run_id      INTEGER,

    -- ===== THE EVENT =====
    idempotency_key      TEXT NOT NULL,          -- hazard (a); UNIQUE below
    -- THE MANDATE'S SESSION ON EVERY KIND -- three facts, three homes (R24
    -- MAJOR). `action_session_date` says WHICH SESSION'S MANDATE this row is
    -- about; `recorded_ts` says WHEN THE ANSWER HAPPENED (and is the only time
    -- axis the monthly report reads, section F.3); `broker_snapshot_session`
    -- inside `validity_detail` says WHEN THE BROKER VIEW WAS TAKEN. Per kind:
    --   place / decline -- the VALIDATED session anchor. The mandate was
    --                      prepared FOR that session, so anchor and mandate
    --                      session are the same value.
    --   validity        -- SERVER-COPIED from the parent `place` row, NEVER
    --                      taken from the payload and NEVER the submitted
    --                      anchor. A validity row answers for THAT order, and
    --                      the aged prompt is the normal case, so an anchor-
    --                      derived value would file a July mandate under
    --                      August. Enforced by the repo + a trigger twin of
    --                      trg_loi_validity_parent_insert asserting
    --                      NEW.action_session_date = parent.action_session_date.
    --   cancel / attest -- the VALIDATED session anchor. There is no parent
    --                      mandate row to copy from, and the operator's action
    --                      is about the panel as of that session.
    action_session_date  TEXT NOT NULL,
    recorded_ts          TEXT NOT NULL,          -- SERVER-STAMPED at POST, never from the payload
    surface              TEXT NOT NULL,
    intent_kind          TEXT NOT NULL,          -- place | decline | cancel | attest | validity
    decline_reason       TEXT,                   -- required iff intent_kind='decline'
    attested_disposition TEXT,                   -- required iff intent_kind='attest'
    -- THE VALIDITY PARENT LINK (Codex R4 MAJOR 3). A `validity` row answers for
    -- ONE specific `place` intent, not for "the latch". A latch can have more
    -- than one place/validity cycle (he places, it is rejected, he re-places),
    -- and a latest-by-latch read would attach a later answer to an earlier
    -- order and RETROACTIVELY change a reported outcome. Self-referencing FK,
    -- RESTRICT for the same reason candidate_id is: the ledger is append-only
    -- and a severed parent is a silent corruption.
    validated_place_intent_id INTEGER
        REFERENCES latch_order_intents(intent_id) ON DELETE RESTRICT,

    -- ===== THE FRAMEWORK'S COMPUTED ORDER (stored VERBATIM -- A.3) =====
    framework_order_type  TEXT,                  -- STOP_LIMIT | LIMIT; NULL only for attest/cancel
    framework_duration    TEXT,
    framework_stop_price  REAL,                  -- NULL in the pullback regime (no stop leg)
    framework_limit_price REAL,
    framework_quantity    INTEGER,

    -- ===== THE DERIVATION INPUTS THAT CAN DRIFT (A.4) =====
    derivation_zone_cap_pct         REAL,
    derivation_sizing_equity        REAL,
    derivation_max_risk_pct         REAL,
    derivation_position_pct_cap     REAL,
    -- A REAL FK, not a bare integer (Codex R6 MAJOR 2) -- and RESTRICT, not
    -- SET NULL (Codex R13 CRITICAL). The R6 draft chose SET NULL on
    -- audit-linkage grounds and that DIRECTLY CONTRADICTED the R7 immutability
    -- trigger one section later: a SET NULL cascade is an UPDATE on this table,
    -- and trg_loi_no_update ABORTs every UPDATE -- so deleting a referenced
    -- risk_policy row would have raised instead of nulling, and the plan's own
    -- test for that behaviour could never have passed. RESTRICT is also the
    -- semantically right answer independently: risk_policy rows are SUPERSEDED
    -- (effective_to + superseded_by_policy_id), never deleted, so RESTRICT
    -- forbids only something production does not do -- while SET NULL bought
    -- tolerance for an event that cannot occur, at the cost of a contradiction
    -- with the table's central invariant.
    derivation_risk_policy_id       INTEGER
        REFERENCES risk_policy(policy_id) ON DELETE RESTRICT,
    derivation_sizing_basis         TEXT,        -- limit_price | pivot
    derivation_regime_close         REAL,        -- NULL = regime was undeterminable
    derivation_regime_close_session TEXT,        -- the session that close is DATED (21-G honesty)
    -- RENDERED ON THE CARD, THEREFORE ANCHORED AND STORED (A.4, Codex R27
    -- MAJOR). real_equity moves with every exit and cash movement while
    -- sizing_equity can stay pinned at the floor -- so without these the row
    -- records a derivation line the operator never saw. The nightly count is
    -- NULLABLE because A.2's divergence note is absent when no
    -- daily_recommendations row exists for the fire.
    derivation_real_equity                   REAL,
    derivation_equity_floor                  REAL,
    derivation_nightly_recommendation_shares INTEGER,

    -- ===== THE OPERATOR'S ACTUAL PARAMS (nullable) =====
    actual_order_type      TEXT,
    actual_duration        TEXT,
    actual_stop_price      REAL,
    actual_limit_price     REAL,
    actual_quantity        INTEGER,
    actual_broker_order_id TEXT,                 -- hazards (c) + (d)

    -- ===== ORDER-VALIDITY OUTCOME (B3 item 5) =====
    -- Carried on `validity` ROWS ONLY. The table is APPEND-ONLY, so a `place`
    -- row can never be updated with an outcome learned later; a separate
    -- append-only `validity` intent is the only shape that both records the
    -- outcome and preserves the append-only property (Codex R3 MAJOR 3 -- as
    -- first drafted these two columns were literally unwritable).
    validity_outcome TEXT,
    validity_detail  TEXT,

    CHECK (intent_kind IN ('place','decline','cancel','attest','validity')),
    CHECK (surface IN ('latch_panel')),
    CHECK (framework_order_type IS NULL OR framework_order_type IN ('STOP_LIMIT','LIMIT')),
    -- PROVENANCE COLUMNS ARE CONSTRAINED, not merely present (Codex R6 MAJOR 2).
    -- An audit-grade column that accepts anything is a column that will later
    -- look authoritative while holding a typo.
    CHECK (framework_duration IS NULL OR framework_duration = 'GOOD_TILL_CANCEL'),
    -- CANONICALISED BEFORE PERSISTENCE (R19 MAJOR). Brokers render GTC where
    -- the framework stores GOOD_TILL_CANCEL, so an uncanonicalised actual would
    -- report a DURATION MISMATCH on a semantically identical order -- a false
    -- divergence in the one metric this ledger exists to compute.
    CHECK (actual_duration IS NULL OR actual_duration IN
           ('GOOD_TILL_CANCEL','DAY','FILL_OR_KILL','IMMEDIATE_OR_CANCEL',
            'END_OF_WEEK','END_OF_MONTH','NEXT_END_OF_MONTH','UNKNOWN')),
    -- The ACTUAL order type is an ENUM, not free text, and the stop leg is
    -- conditioned on it exactly as the framework side is. Without this an
    -- accepted STOP_LIMIT can be stored with NO actual stop and still enter the
    -- agreement denominator, where compute_order_delta reports the stop leg
    -- UNKNOWN instead of a clean match; the reverse bad shape (a LIMIT carrying
    -- a stop) is equally storable.
    CHECK (actual_order_type IS NULL OR actual_order_type IN
           ('STOP_LIMIT','LIMIT','UNKNOWN')),
    -- A NON-ACCEPTED VALIDITY ROW CARRIES NO OBSERVED ORDER AT ALL (Codex R29
    -- MAJOR). The CHECKs required a COMPLETE actual side for
    -- `accepted_by_broker` and said nothing about the other three outcomes -- so
    -- a raw append could store `not_submitted` BESIDE an observed broker order
    -- id and a full actual limit/quantity. The report excludes it from the
    -- agreement denominator, but the ROW still sits in an append-only ledger
    -- carrying an authoritative-looking exact linkage that CONTRADICTS its own
    -- verdict, and section G.4 tells a future reader that a broker order id on a
    -- validity row IS the exact linkage. An outcome and its evidence must not be
    -- able to disagree.
    -- If a "visibly rejected order" evidence kind is ever wanted, it gets its
    -- own outcome value with its own CHECKs and its own report bucket -- section
    -- A.0: it would be a different KIND of evidence, not a loosening of this one.
    CHECK (intent_kind <> 'validity'
           OR validity_outcome = 'accepted_by_broker'
           OR (actual_order_type IS NULL AND actual_duration IS NULL
               AND actual_stop_price IS NULL AND actual_limit_price IS NULL
               AND actual_quantity IS NULL
               AND actual_broker_order_id IS NULL)),
    CHECK (validity_outcome <> 'accepted_by_broker'
           OR actual_order_type <> 'STOP_LIMIT' OR actual_stop_price IS NOT NULL),
    CHECK (validity_outcome <> 'accepted_by_broker'
           OR actual_order_type <> 'LIMIT'      OR actual_stop_price IS NULL),
    CHECK (derivation_sizing_basis IS NULL
           OR derivation_sizing_basis IN ('limit_price','pivot')),
    CHECK (derivation_zone_cap_pct IS NULL OR derivation_zone_cap_pct > 0),
    -- `real_equity` may be ZERO or NEGATIVE and that is not an error -- it is
    -- the account, and it is exactly why the floor exists. So it is bounded by
    -- NOTHING except being present; the floor and the nightly count are bounded
    -- positive like their siblings.
    CHECK (derivation_equity_floor IS NULL OR derivation_equity_floor > 0),
    CHECK (derivation_nightly_recommendation_shares IS NULL
           OR derivation_nightly_recommendation_shares > 0),
    CHECK (derivation_sizing_equity IS NULL OR derivation_sizing_equity > 0),
    CHECK (derivation_max_risk_pct IS NULL OR derivation_max_risk_pct > 0),
    CHECK (derivation_position_pct_cap IS NULL OR derivation_position_pct_cap > 0),
    -- PAIRED NULL. A close without the session it is DATED is exactly the
    -- provenance-free number 21-G exists to eliminate; a session without a
    -- close is a claim about a price that is not there.
    CHECK ((derivation_regime_close IS NULL) = (derivation_regime_close_session IS NULL)),
    CHECK (derivation_regime_close_session IS NULL
           OR COALESCE(length(derivation_regime_close_session) = 10
               AND date(derivation_regime_close_session) IS NOT NULL
               AND date(derivation_regime_close_session)
                   = derivation_regime_close_session
               AND CAST(substr(derivation_regime_close_session, 1, 4) AS INTEGER)
                   BETWEEN 1 AND 9999, 0)),
    CHECK (actual_quantity IS NULL OR actual_quantity > 0),
    -- EVERY PRICE IS POSITIVE (Codex R28 MAJOR). The price columns were shape-
    -- constrained (which kind may carry which leg) and never VALUE-constrained,
    -- so a raw append could store a negative or zero framework or actual price
    -- -- including on an `accepted_by_broker` validity row, which then enters
    -- the agreement DENOMINATOR and reports a delta computed from a price that
    -- cannot exist. Route-level validation is not the answer here for the same
    -- reason it is not the answer anywhere else on this table: it is APPEND-ONLY
    -- and audit-grade, so a bad row is permanent, and the whole posture of the
    -- CHECK block is that raw appends are in scope.
    CHECK (framework_limit_price IS NULL OR framework_limit_price > 0),
    CHECK (framework_stop_price  IS NULL OR framework_stop_price  > 0),
    CHECK (actual_limit_price    IS NULL OR actual_limit_price    > 0),
    CHECK (actual_stop_price     IS NULL OR actual_stop_price     > 0),
    CHECK (framework_quantity IS NULL OR framework_quantity > 0),
    CHECK (attested_disposition IS NULL OR attested_disposition IN
           ('acted_manually','chose_not_to_act','was_away')),
    CHECK (validity_outcome IS NULL OR validity_outcome IN
           ('accepted_by_broker','rejected_by_broker','not_submitted','unknown')),
    -- the three-state contract, enforced in SQL rather than only in Python,
    -- and enforced in BOTH DIRECTIONS (Codex R12 MAJOR 1): a required field
    -- that is merely "required on its own kind" still lets every OTHER kind
    -- carry it, so a `place` row could ship a decline_reason and read as both.
    CHECK (intent_kind <> 'decline' OR (decline_reason IS NOT NULL
           AND length(trim(decline_reason)) > 0)),
    CHECK (intent_kind =  'decline' OR decline_reason IS NULL),
    CHECK (intent_kind =  'attest'  OR attested_disposition IS NULL),
    -- THE STOP LEG IS CONDITIONED ON THE ORDER TYPE. A STOP_LIMIT without its
    -- stop trigger is not the mandate; a LIMIT carrying one is the rejected
    -- FTRE shape. Neither should be storable.
    CHECK (framework_order_type <> 'STOP_LIMIT' OR framework_stop_price IS NOT NULL),
    CHECK (framework_order_type <> 'LIMIT'      OR framework_stop_price IS NULL),
    CHECK (intent_kind <> 'attest'  OR attested_disposition IS NOT NULL),
    -- An ACCEPTED-BY-BROKER validity row must carry a COMPLETE observed order
    -- (Codex R20 MAJOR). The agreement DENOMINATOR requires a known actual
    -- side, and compute_order_delta returns any_difference = None (UNKNOWN)
    -- when any field is missing -- so a row omitting actual_duration would make
    -- FTRE's divergence UNKNOWN rather than a clean quantity mismatch, and the
    -- arc's worked example would still miss the metric it exists to feed.
    -- ...and "complete" means KNOWN and EXACTLY LINKED, not merely non-NULL
    -- (R22 MAJOR). section G.4 claims exact linkage comes from validity rows and
    -- section F.3's denominator requires a KNOWN actual side, so an accepted row
    -- carrying a NULL broker order id or an UNKNOWN type/duration would look
    -- authoritative while satisfying neither claim.
    CHECK (validity_outcome <> 'accepted_by_broker' OR (
           actual_order_type IS NOT NULL AND actual_duration IS NOT NULL
       AND actual_limit_price IS NOT NULL AND actual_quantity IS NOT NULL
       AND actual_broker_order_id IS NOT NULL
       AND actual_order_type IN ('STOP_LIMIT','LIMIT')
       AND actual_duration <> 'UNKNOWN')),
    CHECK (intent_kind <> 'validity' OR (validity_outcome IS NOT NULL
           AND validated_place_intent_id IS NOT NULL
           -- SNAPSHOT CONTEXT IS STRUCTURALLY REQUIRED (R19 MAJOR). The plan
           -- SAYS the snapshot ts / branch / digest are persisted into
           -- validity_detail; without a CHECK a row can be written with none of
           -- it, defeating the audit claim and making the staleness gate
           -- unverifiable after the fact. `validity_detail` carries a JSON
           -- object. THE ROSTER OF REQUIRED KEYS IS THE `json_remove(...)` PATH
           -- LIST BELOW -- that call is the MACHINE-READABLE source of truth,
           -- and `LATCH_BROKER_SNAPSHOT_KEYS` mirrors it under #11 (a test
           -- parses the path list out of this migration and asserts exact set
           -- equality with the constant). NO SITE IN THIS PLAN STATES THE KEY
           -- COUNT: an earlier round added broker_snapshot_session to this
           -- CHECK while three other sites still said "six keys", so the
           -- fragment's emitted set and the row's required set disagreed by one
           -- -- which makes the audit row unwritable. A cardinality is exactly
           -- the kind of fact that goes stale when an adjacent edit lands, so
           -- every other site says "every key in the roster" and names no
           -- number.
           -- They are enforced in the repo + the dataclass validator
           -- under #11 AND in SQL: for an append-only audit ledger "the repo
           -- usually writes it correctly" is not enough, because a raw insert
           -- can append a row the report cannot hydrate and whose staleness
           -- basis is unknowable forever after.
           AND validity_detail IS NOT NULL
           -- ===== THE NULL-PASS DEFENCE, AGAIN, ON JSON (Codex R25 CRITICAL).
           -- The SAME class as C.1.1's date defect, one layer in: a MISSING key
           -- makes json_extract() return NULL, so `length(NULL) = 19` is NULL and
           -- a SQLite CHECK PASSES on NULL. Verified empirically at this writing:
           -- against the presence-and-shape chain written bare, the JSON object
           -- `{}` -- every single key absent -- was ACCEPTED. The whole audit
           -- claim was void. That the class recurred WITHIN THIS PLAN, in a
           -- different syntax, one round after being named, is the argument for
           -- making the guard STRUCTURAL rather than remembering it per-site.
           --
           -- The fix is the two-part wrapper below and it is not optional:
           --   * `COALESCE(<chain>, 0)` turns a NULL verdict into FALSE, so a
           --     missing key REJECTS instead of passing.
           --   * `CASE WHEN json_valid(...) THEN ... ELSE 0 END` gates the
           --     json_* calls, because SQLite does NOT guarantee AND-chain
           --     short-circuit: with a non-JSON value the bare chain raises
           --     OperationalError('malformed JSON') instead of rejecting, so a
           --     test asserting IntegrityError would fail against correct-
           --     looking DDL. CASE *does* short-circuit; verified.
           -- With the wrapper, all of `{}`, a missing single key, a JSON array,
           -- a JSON scalar and a non-JSON string reject as IntegrityError.
           --
           -- VALUE SHAPES, not merely presence (R24 MAJOR). Presence-only checks
           -- let a raw append store an invalid branch, a malformed timestamp, a
           -- non-hex digest or a non-boolean flag, and an append-only ledger
           -- keeps it forever.
           AND CASE WHEN json_valid(validity_detail) THEN COALESCE(
               json_type(validity_detail) = 'object'
           -- EXACTLY SEVEN, NOT AT-LEAST-SEVEN (Codex R27 MAJOR). The plan says
           -- the envelope carries EXACTLY the roster keys and is persisted
           -- VERBATIM; the presence-and-shape chain below only ever enforced
           -- AT LEAST. Extra keys therefore rode along into an append-only audit
           -- row unaudited -- and since `actual_digest` covers only
           -- `broker_snapshot_digest`, two envelopes differing ONLY by extra
           -- content share an idempotency key, so the second is replayed and its
           -- extra content silently dropped instead of rejected.
           -- `json_remove` of the seven known paths must leave the EMPTY object.
           -- BOTH HALVES ARE REQUIRED, exactly as in C.1.1: json_remove closes
           -- EXTRA and is BLIND to MISSING (removing an absent path is a no-op,
           -- so `{}` passes it), while the shape chain closes MISSING and is
           -- blind to EXTRA. Verified empirically: with json_remove alone, a
           -- seven-key object passes, an eight-key object rejects, and BOTH the
           -- empty object and a six-key object still pass.
           AND json_remove(validity_detail,
                   '$.broker_snapshot_ts', '$.broker_snapshot_branch',
                   '$.broker_snapshot_digest', '$.broker_snapshot_session',
                   '$.attributable_order_count', '$.exact_framework_match_count',
                   '$.indeterminate') = '{}'
           AND length(json_extract(validity_detail, '$.broker_snapshot_ts')) = 19
           AND json_extract(validity_detail, '$.broker_snapshot_ts') GLOB
               '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
           -- ALL THREE PREDICATES AT THIS SITE TOO (Codex R27 MAJOR). The
           -- IS NOT NULL leg was omitted here and the site leaned on the outer
           -- COALESCE instead -- which happens to reject, but means C.1.1's
           -- "one mechanism, three predicates, every site" was not actually
           -- uniform, and a later edit to the wrapper would silently weaken it.
           AND date(substr(json_extract(validity_detail,'$.broker_snapshot_ts'),1,10))
               IS NOT NULL
           AND date(substr(json_extract(validity_detail,'$.broker_snapshot_ts'),1,10))
               = substr(json_extract(validity_detail,'$.broker_snapshot_ts'),1,10)
           AND CAST(substr(json_extract(validity_detail,'$.broker_snapshot_ts'),1,4)
                    AS INTEGER) BETWEEN 1 AND 9999
           AND CAST(substr(json_extract(validity_detail,'$.broker_snapshot_ts'),12,2)
                    AS INTEGER) <= 23
           AND CAST(substr(json_extract(validity_detail,'$.broker_snapshot_ts'),15,2)
                    AS INTEGER) <= 59
           AND CAST(substr(json_extract(validity_detail,'$.broker_snapshot_ts'),18,2)
                    AS INTEGER) <= 59
           -- (the branch enum is asserted ONCE, below, and it is the TWO-valued
           -- answer vocabulary -- not the three-valued render vocabulary)
           AND length(json_extract(validity_detail, '$.broker_snapshot_digest')) = 64
           AND json_extract(validity_detail, '$.broker_snapshot_digest')
               NOT GLOB '*[^0-9a-f]*'
           AND length(json_extract(validity_detail, '$.broker_snapshot_session')) = 10
           AND date(json_extract(validity_detail, '$.broker_snapshot_session'))
               IS NOT NULL
           -- ROUND-TRIP TOO, not IS NOT NULL alone -- the C.1.1 pair, applied
           -- here as well: without it '2026-02-30' NORMALISES and is accepted.
           AND date(json_extract(validity_detail, '$.broker_snapshot_session'))
               = json_extract(validity_detail, '$.broker_snapshot_session')
           AND CAST(substr(
                   json_extract(validity_detail,'$.broker_snapshot_session'),1,4)
                    AS INTEGER) BETWEEN 1 AND 9999
           -- A `validity` ROW MAY NOT CARRY AN `unavailable` SNAPSHOT (Codex R26
           -- MAJOR). Section E is explicit that an UNKNOWN order book renders NO
           -- validity prompt in either direction -- so a persisted validity row
           -- whose own snapshot says the book was unavailable is a row asserting
           -- an execution outcome it had no evidence for, and this ledger is
           -- append-only, so it would assert it forever. The three-valued enum
           -- above is the FRAGMENT's render vocabulary; the ANSWER vocabulary is
           -- two-valued. (Section A.0 again: the render status and the persisted
           -- answer are measured differently and do not share one enum.)
           -- MIRRORED UNDER #11 LIKE EVERY OTHER ENUM CHECK (Codex R28 MAJOR).
           -- This is a schema enum that lived only in SQL: section I's constants
           -- list and Task 1's "every enum CHECK" parse-and-compare test both
           -- omitted it because it is expressed as a JSON predicate rather than
           -- a column CHECK, which is a difference in SYNTAX and not in kind.
           -- TWO constants, because there are two vocabularies (above):
           --   LATCH_BROKER_SNAPSHOT_RENDER_BRANCHES    = presence/absence/unavailable
           --   LATCH_BROKER_SNAPSHOT_PERSISTED_BRANCHES = presence/absence
           -- The fragment emits from the RENDER set, the handler + dataclass
           -- validate against the PERSISTED set, this CHECK mirrors the
           -- PERSISTED set, and a test asserts PERSISTED < RENDER (a strict
           -- subset -- equality would mean the narrowing was silently undone).
           AND json_extract(validity_detail, '$.broker_snapshot_branch')
               IN ('presence','absence')
           AND json_type(validity_detail, '$.attributable_order_count') = 'integer'
           AND json_extract(validity_detail, '$.attributable_order_count') >= 0
           AND json_type(validity_detail, '$.exact_framework_match_count') = 'integer'
           AND json_extract(validity_detail, '$.exact_framework_match_count') >= 0
           AND json_type(validity_detail, '$.indeterminate')
               IN ('true','false'), 0) ELSE 0 END)),
    -- `validated_place_intent_id` is ALSO folded into the idempotency key
    -- (section G.1), so two place intents on one latch cannot collide on an
    -- identical answer. Multiple validity rows for ONE parent stay LEGAL and
    -- are a feature: a CORRECTION (he answered "rejected", then learns it
    -- filled) is a NEW row, which is what append-only requires. Resolution is
    -- the LATEST by (recorded_ts, intent_id) FOR THAT PARENT -- stated here
    -- because "latest validity row" without "for that parent" is exactly the
    -- R4 MAJOR 3 defect in a smaller box.
    CHECK (intent_kind =  'validity' OR (validity_outcome IS NULL
           AND validity_detail IS NULL AND validated_place_intent_id IS NULL)),
    -- ===== SHAPE EXCLUSION: THREE CHECKS, ONE RULE =====
    -- Each intent kind carries exactly the columns its MEANING requires, so no
    -- row can read as two things at once and be counted twice by the report.
    --
    --   place    -- a DECISION about a prepared order: framework + derivation,
    --               NO actual params, NO broker order id (it observed nothing).
    --   decline  -- also a DECISION about a prepared order, so it carries the
    --               SAME framework + derivation block. Erasing it would leave RD
    --               unable to audit WHAT was declined without recomputing it,
    --               which is what section A.3 stores the framework side verbatim
    --               to prevent. Declines are excluded from execution-parity
    --               ORDER rows by `intent_kind`, never by erasing their subject.
    --   validity -- an OBSERVATION: the actual params + the broker order id +
    --               the verdict, and NO framework/derivation block. It MUST be
    --               able to carry a DIVERGENT observed order (FTRE: framework
    --               LIMIT 18.89 / 9 sh vs actual LIMIT 18.89 / 10 sh) or the
    --               ledger could record agreements and never a divergence, which
    --               is the one thing it exists to measure.
    --   cancel / attest -- neither: no framework, no derivation, no actual order
    --               params. `actual_broker_order_id` IS allowed (a cancel
    --               REQUIRES it, hazard (c); an attest about a self-placed order
    --               may carry it).
    --
    -- The first CHECK is keyed on the ORDER-BEARING kinds rather than on a list
    -- of the others, so a future intent kind is excluded BY DEFAULT.
    CHECK (intent_kind IN ('place','decline','validity') OR (
           framework_order_type IS NULL AND framework_duration IS NULL
       AND framework_stop_price IS NULL AND framework_limit_price IS NULL
       AND framework_quantity IS NULL
       AND derivation_zone_cap_pct IS NULL AND derivation_sizing_equity IS NULL
       AND derivation_max_risk_pct IS NULL AND derivation_position_pct_cap IS NULL
       AND derivation_risk_policy_id IS NULL AND derivation_sizing_basis IS NULL
       AND derivation_regime_close IS NULL
       AND derivation_regime_close_session IS NULL
       AND derivation_real_equity IS NULL AND derivation_equity_floor IS NULL
       AND derivation_nightly_recommendation_shares IS NULL
       AND actual_order_type IS NULL AND actual_duration IS NULL
       AND actual_stop_price IS NULL AND actual_limit_price IS NULL
       AND actual_quantity IS NULL)),
    -- `place` and `decline` carry NO actual params (a decision is not an
    -- observation); `validity` carries actual params and NO framework block.
    CHECK (intent_kind NOT IN ('place','decline') OR (
           actual_order_type IS NULL AND actual_duration IS NULL
       AND actual_stop_price IS NULL AND actual_limit_price IS NULL
       AND actual_quantity IS NULL)),
    -- ...and a `validity` row carries NO framework/derivation block: it
    -- reports an OBSERVATION, never a prepared order.
    CHECK (intent_kind <> 'validity' OR (
           framework_order_type IS NULL AND framework_duration IS NULL
       AND framework_stop_price IS NULL AND framework_limit_price IS NULL
       AND framework_quantity IS NULL
       AND derivation_zone_cap_pct IS NULL AND derivation_sizing_equity IS NULL
       AND derivation_max_risk_pct IS NULL AND derivation_position_pct_cap IS NULL
       AND derivation_risk_policy_id IS NULL AND derivation_sizing_basis IS NULL
       AND derivation_regime_close IS NULL
       AND derivation_regime_close_session IS NULL
       AND derivation_real_equity IS NULL AND derivation_equity_floor IS NULL
       AND derivation_nightly_recommendation_shares IS NULL)),
    -- R17 MAJOR: a `place` row must CARRY the whole drift-capable derivation
    -- block, not merely be permitted to. Without this a place row can ship an
    -- authoritative-looking order with NULL sizing provenance -- the "four bare
    -- numbers" B1 exists to prevent, one layer down. The regime pair is included
    -- because the form is WITHHELD when the regime is undeterminable (section
    -- B.2), so an OFFERED order always had one.
    CHECK (intent_kind NOT IN ('place','decline') OR (
           derivation_zone_cap_pct IS NOT NULL
       AND derivation_sizing_equity IS NOT NULL
       AND derivation_max_risk_pct IS NOT NULL
       AND derivation_position_pct_cap IS NOT NULL
       AND derivation_sizing_basis IS NOT NULL
       AND derivation_regime_close IS NOT NULL
       AND derivation_regime_close_session IS NOT NULL
       -- the two card-rendered equity values are REQUIRED for the same reason
       -- the rest of the block is (Codex R27 MAJOR).
       AND derivation_real_equity IS NOT NULL
       AND derivation_equity_floor IS NOT NULL)),
    -- EXACTLY TWO DERIVATION COLUMNS ARE LEGITIMATELY NULLABLE ON A place OR
    -- decline ROW, and both have a REASON rather than an omission (Codex R28
    -- MAJOR flagged the third, `derivation_risk_policy_id`, as an inconsistency
    -- between this CHECK and Task 1's "every derivation column is required"
    -- enumeration -- correctly, and the resolution is to name the exemptions
    -- here so the two can never disagree again):
    --   derivation_nightly_recommendation_shares -- a fire with no
    --     daily_recommendations row has none, and the card renders no
    --     divergence note for it.
    --   derivation_risk_policy_id -- the RATE fed to compute_shares comes from
    --     cfg.risk.max_risk_pct, NOT from the policy row (section D.2), so a
    --     prepared order is fully computable with no active policy row and the
    --     form is NOT withheld for one. The id is recorded for PROVENANCE. The
    --     card therefore renders it CONDITIONALLY and, when absent, renders an
    --     explicit "no active risk_policy row" line rather than a blank -- an
    --     unlabelled gap would be the quiet-reduction failure section A.1.1
    --     forbids.
    -- Every OTHER derivation column is required above. The two exempt columns
    -- are the ROSTER `DERIVATION_NULLABLE_ON_DECISION` in
    -- swing/latches/constants.py; Task 1 derives the required set as
    -- {every derivation_* column in the schema} - DERIVATION_NULLABLE_ON_DECISION
    -- and states no cardinality, so adding a derivation column extends the
    -- required set automatically and adding an EXEMPTION is a deliberate edit
    -- to a named constant with a reviewer.
    -- HAZARD (c) MADE STRUCTURAL: a cancel MUST name one broker order. There is
    -- no by-ticker cancel path anywhere and the schema makes one unwritable.
    CHECK (intent_kind <> 'cancel'  OR (actual_broker_order_id IS NOT NULL
           AND length(trim(actual_broker_order_id)) > 0)),
    -- ...and it is never BLANK when present, on any kind (R19 MAJOR).
    CHECK (actual_broker_order_id IS NULL
           OR length(trim(actual_broker_order_id)) > 0),
    -- A broker order id is an OBSERVATION. `place` and `decline` are DECISIONS
    -- about a prepared order and have observed nothing, so allowing them a
    -- broker id blurs exact linkage against inference and would let a plain
    -- accept row read as broker-confirmed (R19 MAJOR).
    CHECK (intent_kind NOT IN ('place','decline')
           OR actual_broker_order_id IS NULL),
    -- a `place` or `decline` records a complete order or it is not a record of
    -- a decision ABOUT an order
    CHECK (intent_kind NOT IN ('place','decline') OR (framework_order_type IS NOT NULL
           AND framework_limit_price IS NOT NULL AND framework_quantity IS NOT NULL
           AND framework_quantity > 0 AND framework_duration IS NOT NULL)),
    -- EVERY date/time CHECK CARRIES AN EXPLICIT `IS NOT NULL` (R24 CRITICAL).
    -- A SQLite CHECK PASSES when its expression evaluates to NULL, and
    -- date('2026-99-99') IS NULL -- so `date(x) = x` evaluates to NULL and
    -- ACCEPTS a length-correct invalid date. Verified empirically: a table with
    -- CHECK (length(d)=10 AND date(d)=d) accepts '2026-99-99'; adding
    -- `date(d) IS NOT NULL` rejects it. BOTH halves are required: the
    -- round-trip equality catches the NORMALISING case ('2026-02-30' ->
    -- '2026-03-02', non-NULL but not equal) and the IS NOT NULL catches the
    -- INVALID case. Neither alone is sufficient.
    CHECK (COALESCE(length(detection_date) = 10
           AND date(detection_date) IS NOT NULL
           AND date(detection_date) = detection_date
           AND CAST(substr(detection_date, 1, 4) AS INTEGER) BETWEEN 1 AND 9999, 0)),
    CHECK (COALESCE(length(action_session_date) = 10
           AND date(action_session_date) IS NOT NULL
           AND date(action_session_date) = action_session_date
           AND CAST(substr(action_session_date, 1, 4) AS INTEGER) BETWEEN 1 AND 9999, 0)),
    -- `recorded_ts` DRIVES THE MONTHLY REPORT'S CUTOFF AND ORDERING (section
    -- F.3), so an unconstrained TEXT column lets a raw insert or a repo bug
    -- silently misbucket a monthly parity read while looking authoritative
    -- (R19 MAJOR). Local ISO seconds, exactly: YYYY-MM-DDTHH:MM:SS.
    --
    -- THE `datetime(x) = replace(x,'T',' ')` FORM DOES NOT ENFORCE THAT
    -- CONTRACT (Codex R25 MAJOR). Verified empirically at this writing, it
    -- ACCEPTS both '2026-07-28 12:00:00' (a SPACE separator -- replace() is a
    -- no-op, so it compares equal to itself) and '2026-07-28T24:00:00' (SQLite
    -- does NOT normalise hour 24 away; datetime() echoes '2026-07-28 24:00:00'
    -- and the replace matches). A space-separated stamp then sorts differently
    -- from a T-separated one in the exact ORDER BY the monthly report uses, and
    -- hour 24 is a stamp no clock produced. So the shape is pinned by GLOB (one
    -- expression fixing all 19 positions, every digit, both colons and the T),
    -- the DATE HALF gets C.1.1's BOTH-halves pair, and each time component gets
    -- an explicit range. `datetime(x) IS NOT NULL` is kept as a belt.
    -- Empirically: T12:00:00 and T23:59:59 accepted; the space form,
    -- T24:00:00, T12:60:00, 2026-99-99T.., 2026-02-30T.. and non-digits all
    -- rejected. `COALESCE(..., 0)` wraps it for the same NULL-pass reason as
    -- the envelope CHECK above.
    CHECK (COALESCE(
           length(recorded_ts) = 19
           AND recorded_ts GLOB
               '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'
           AND datetime(recorded_ts) IS NOT NULL
           AND date(substr(recorded_ts, 1, 10)) IS NOT NULL
           AND date(substr(recorded_ts, 1, 10)) = substr(recorded_ts, 1, 10)
           AND CAST(substr(recorded_ts, 1, 4) AS INTEGER) BETWEEN 1 AND 9999
           AND CAST(substr(recorded_ts, 12, 2) AS INTEGER) <= 23
           AND CAST(substr(recorded_ts, 15, 2) AS INTEGER) <= 59
           AND CAST(substr(recorded_ts, 18, 2) AS INTEGER) <= 59, 0)),
    CHECK (evaluation_run_id > 0),
    CHECK (length(trim(ticker)) > 0),

    UNIQUE (idempotency_key)
);
CREATE INDEX ix_loi_candidate_id        ON latch_order_intents(candidate_id);
CREATE INDEX ix_loi_ticker_detection    ON latch_order_intents(ticker, detection_date);
CREATE INDEX ix_loi_action_session_date ON latch_order_intents(action_session_date);
```

Plus the SAME two identity-coherence triggers `0032` defines (insert + update), pointed at this table — the
denormalised identity copies must not be able to disagree with `candidate_id`, for the same RD-finding-4
reason. **Plus a THIRD trigger pair for the validity parent link (Codex R6 MAJOR 1):** the self-FK only
prevents a DANGLING pointer — on its own it happily accepts a `validity` row pointing at a `decline`, a
`cancel`, another `validity`, or a `place` row belonging to a DIFFERENT latch, any of which attaches an
execution outcome to the wrong order and makes the ledger self-contradictory. A CHECK cannot reference another
row, so:

```sql
CREATE TRIGGER trg_loi_validity_parent_insert
BEFORE INSERT ON latch_order_intents
FOR EACH ROW WHEN NEW.validated_place_intent_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT,
        'latch_order_intents validity parent must be a place row on the same latch '
        'and the child must carry the parent''s action_session_date')
    WHERE NOT EXISTS (
        SELECT 1 FROM latch_order_intents parent
        WHERE parent.intent_id  = NEW.validated_place_intent_id
          AND parent.intent_kind = 'place'
          AND parent.candidate_id = NEW.candidate_id
          -- THE SERVER-COPY, ENFORCED RATHER THAN ASSERTED (Codex R25 MAJOR).
          -- section C.2 declares that a `validity` row's action_session_date IS
          -- the parent place row's -- and the trigger checked parent KIND and
          -- CANDIDATE while leaving the session leg to the repo. A raw insert
          -- (or a handler that reached for the submitted anchor, which is the
          -- ONE mistake section G.2 names as most likely) could then file an
          -- August answer under an August mandate date while pointing at a July
          -- order, and every monthly read afterwards would attribute the mandate
          -- to the wrong month. It is one predicate; the claim is worth having
          -- enforced by the same mechanism that enforces the other two legs.
          AND parent.action_session_date = NEW.action_session_date);
END;
```

with the matching `BEFORE UPDATE OF validated_place_intent_id, candidate_id, action_session_date` twin.
Keying the LATCH coherence on `candidate_id` (the immutable latch surrogate) is deliberate — but note that
the session leg is now an EQUALITY, not an absence, and the two are not in tension: **an aged prompt is
answered in a LATER session, and that later session is recorded in `recorded_ts`, not in
`action_session_date`.** The mandate session is the parent's by definition (§C.2), so requiring the copy is
what makes the aged prompt recordable CORRECTLY rather than what blocks it. A test asserts the normal aged
case — a `place` in session N, its `validity` child written in session N+20 carrying
`action_session_date` = N and `recorded_ts` in N+20 — is ACCEPTED, and that the same child carrying
`action_session_date` = N+20 is REJECTED.

**Plus an IMMUTABILITY BARRIER (Codex R7 MAJOR 3).** The plan called this table append-only and audit-grade
and then relied on convention to keep it that way — the same convention `reconciliation_corrections` relies
on. For a ledger whose entire value is that *history does not move*, convention is not enough: one bug or one
manual `UPDATE` silently rewrites a month RD has already read.

```sql
CREATE TRIGGER trg_loi_no_update BEFORE UPDATE ON latch_order_intents
BEGIN SELECT RAISE(ABORT, 'latch_order_intents is append-only: record a new row'); END;
CREATE TRIGGER trg_loi_no_delete BEFORE DELETE ON latch_order_intents
BEGIN SELECT RAISE(ABORT, 'latch_order_intents is append-only: rows are never deleted'); END;
```

**Consequence, and it is binding on every FK this table declares:** on an UPDATE-forbidden table
`ON DELETE SET NULL` is UNIMPLEMENTABLE — the cascade IS an UPDATE and this trigger aborts it. So every FK
here is `ON DELETE RESTRICT`, and a test asserts no `SET NULL` appears in the table's DDL. (This is exactly
how the R13 CRITICAL was found: two fixes written five rounds apart, each locally correct, contradicting each
other at the seam.)

This is STRICTER than the in-tree `reconciliation_corrections` precedent, deliberately — that table needs
`UPDATE` for its `superseded_by_correction_id` chain, and this one needs nothing of the kind: every
correction here is already a new row (the validity-correction case, §C.2). It also makes the
`ON DELETE RESTRICT` FKs redundant-but-harmless belts, and it means the R6-M1 validity-parent UPDATE trigger
can never fire in practice — kept anyway, because a defence that depends on another defence still holding is
not a defence. Tests assert both aborts, and assert the error message names the append-only rule so a future
maintainer hitting it learns the reason rather than working around it.

`UPDATE schema_version SET version = 33;` inside the single explicit `BEGIN; ... COMMIT;` (gotcha #9).

**Column count: the DDL above is authoritative** (R23 MINOR — a hand-maintained count drifted from it and
will again; the migration test asserts the column list, not a number). The 21-A plan's §C.2 estimated "roughly
18 columns about a different subject". The extra columns fall into exactly four GROUPS, and the group is
the unit of justification — **no per-group count is stated here, because every count this plan has stated
about itself has gone stale, and the migration test asserts the column LIST anyway:** the derivation block
(the sizing and regime inputs, which are B1's whole point, plus the card-rendered values §A.4 adds so the row
can reconstruct what the operator actually saw), the actual-params block (B3's whole point), the idempotency
key, and the validity parent link. Every one is justified above; nothing is speculative.
**CHARC's "minimal" gate should be told the derivation block GREW during review and why:** the alternative
was not a smaller table but a card that renders un-audited numbers inside an audited block, which is a
different and worse kind of small. If CHARC still judges
this past "minimal", the compressible group is the derivation block, which could collapse into one JSON
envelope — the plan does NOT recommend that (a JSON blob defeats the CHECKs, defeats indexing, and is the
`structural_evidence_json` shape the Phase-12 gotchas already burned us on). The honest cheaper option, if
one is wanted, is to STOP RENDERING `real_equity` and the nightly divergence note on the card — smaller
table, smaller claim, and §A.4's restated rule permits it explicitly.

### C.3 What does NOT ride `0033`

- No `latches` registry table (21-A §C.2's promotion path stays open and stays deterministic).
- Not the banked `fills_trades_price_divergence` taxonomy type — it takes the next free number, per the 21-A A3
  ruling that it keeps its own migration.
- No column on `trades`, `fills`, or any Phase-7 table.

---

## D. The prepared order (B1) — SHOW THE DERIVATION

### D.1 The pure computation — `swing/latches/order_intent.py`

```python
@dataclass(frozen=True)
class PreparedOrder:
    order_type: str            # STOP_LIMIT | LIMIT
    duration: str              # GOOD_TILL_CANCEL
    stop_price: float | None   # the frozen pivot in the breakout regime; None in pullback
    limit_price: float         # the zone cap
    quantity: int
    # the DERIVATION, carried with the numbers so the renderer cannot show one
    # without the other (the D25 lesson: four bare numbers invite click-through)
    derivation: OrderDerivation

@dataclass(frozen=True)
class OrderDerivation:
    latched_pivot: float
    latched_initial_stop: float
    zone_cap_pct: float
    fire_evaluation_run_id: int
    fire_session: str          # the FIRE's action_session_date
    fire_candidate_id: int
    regime_order_type: str | None
    regime_close: float | None
    regime_close_session: str | None
    sizing_basis: str          # limit_price (A.2) | pivot
    sizing_basis_price: float
    sizing_equity: float
    sizing_equity_source: str  # "starting_equity + realized P&L + net cash, floored at ..."
    real_equity: float
    equity_floor: float
    max_risk_pct: float
    position_pct_cap: float
    risk_policy_id: int | None
    risk_per_share: float
    max_risk_dollars: float
    shares_by_risk: int
    shares_by_position_cap: int
    binding_constraint: str    # SizingResult.constraint
    nightly_recommendation_shares: int | None   # the A.2 divergence, surfaced

@dataclass(frozen=True)
class PreparedOrderResult:
    """EXACTLY ONE of these is non-None (enforced in __post_init__).

    A bare `PreparedOrder | None` return CANNOT carry the withheld reason the
    panel is required to render (Codex R3 MAJOR 4) -- and the withheld branch is
    the CURRENT live state (section B.3), so it is the branch that must be
    expressive, not the afterthought.
    """
    order: PreparedOrder | None
    withheld_reason: str | None       # LATCH_ORDER_WITHHELD_REASONS
    withheld_detail: str              # display-ready; "" when an order is present

def compute_prepared_order(*, latch, regime_order_type, regime_close,
                           regime_close_session, sizing_inputs) -> PreparedOrderResult
```

`withheld_reason` is `regime_undeterminable` when `regime_order_type is None` (§B.2), `sizing_infeasible`
when `SizingResult.feasible` is False, and `sizing_degenerate` if `compute_shares` raises. The frozenset
`LATCH_ORDER_WITHHELD_REASONS` rides the #11 mirror discipline with everything else in Task 1.

**The computation itself:**

| field | derivation |
|---|---|
| `order_type` | `expected_mandate_order_type(latched_pivot=..., last_close=...)` — the 21-A seam, never re-implemented |
| `duration` | `GOOD_TILL_CANCEL` (the only member of `MANDATE_ORDER_DURATIONS`) |
| `stop_price` | `latched_pivot` when `STOP_LIMIT`; `None` when `LIMIT` (a buy stop below the market is the FTRE rejection) |
| `limit_price` | **`floor(latch.zone_cap * 100) / 100`** — the zone cap QUANTIZED DOWN to whole cents. See below; this is NOT the raw `round(pivot * 1.03, 4)` |
| `quantity` | `compute_shares(entry=limit_price, stop=latched_initial_stop, equity=sizing_equity, max_risk_pct=..., position_pct_cap=...).shares` (A.2) |

**THE LIMIT PRICE IS QUANTIZED TO WHOLE CENTS, BY FLOOR, AND THAT ONE VALUE IS USED EVERYWHERE (Codex R29
MAJOR).** The plan carried TWO values for one field: §D.1 said `limit_price = latch.zone_cap` — FTRE's
`round(18.34 * 1.03, 4) = 18.8902` — and the §C.2 raw fixture stored `18.8902`, while §D.3's card, §D.4's
delta and Task 2 all say `LIMIT 18.89`. Both cannot be "the framework's order stored verbatim as the operator
saw it", which is this arc's central claim.

- **Whole cents, because that is the only price the order could actually be.** A US equity limit order is
  penny-priced; `18.8902` is not a price the operator could enter, and this arc exists to put *the order he
  would place* in front of him. Rendering four decimals would make the card a number he must silently
  re-round himself — the click-through invitation §D.3 exists to prevent.
- **FLOOR, not round-half-up, and the reason is the CAP SEMANTIC.** The zone cap is a MAXIMUM (`pivot * 1.03`
  is the top of the buy zone), so a quantization that can move the price UP can push the order above the
  zone. Round-half-up does that whenever the cap's third decimal is >= 5 (a cap of `18.8952` becomes
  `18.90 > 18.8952`). **FTRE does NOT exhibit it** — `18.8902` rounds down either way — which is exactly why
  the rule has to be stated rather than inferred from the worked example.
- **The sizing arithmetic is UNCHANGED, verified under all three candidates.** raw `18.8902` -> risk/share
  `4.0102`; floor `18.89` -> `4.0100`; both give `floor(37.50 / risk) = 9` shares, position-cap 59, RISK
  binds, worst-case `$36.09 = 0.481%` of sizing equity — inside the 0.5% policy cap in every case. So this
  fix does not disturb §A.2's recommendation or its 9-vs-10 discriminator.
- **ONE value, used in ALL of:** `PreparedOrder.limit_price`, the card, the hidden anchor, `anchor_digest`,
  the stored `framework_limit_price`, `compute_shares`'s entry, `compute_order_delta`, and every fixture.
  `derivation_zone_cap_pct` plus the `candidate_id`-pinned pivot still make the un-quantized cap exactly
  recomputable, so nothing is lost and no extra column is needed.
- A test asserts `PreparedOrder.limit_price == 18.89` for FTRE **and** that a synthetic cap of `18.8952`
  quantizes to `18.89`, not `18.90` — the round-half-up implementation passes the first and FAILS the second.

`compute_shares` raises `ValueError` when `stop >= entry`. `Latch.__post_init__` already guarantees
`latched_initial_stop < latched_pivot < zone_cap`, so it cannot fire — but the call is guarded anyway and a
raise degrades to a withheld form with `reason='sizing_degenerate'` (A6).

### D.2 The sizing equity, named exactly (B1: "which equity figure")

```
real_equity  = current_equity(starting_equity=cfg.account.starting_equity,
                              exits=list_all_exitshape_via_fills(conn),
                              cash_movements=list_cash(conn))
sizing_equity = sizing_equity(real_equity=real_equity, floor=cfg.account.risk_equity_floor)
```

Both are read-only imports from `swing/trades/equity.py`. This matches what the **nightly briefing and the
dashboard** use (`swing/web/view_models/dashboard.py:721`, `swing/cli.py:428`) and deliberately NOT what
`POST /trades/sizing-hint` uses (`swing/web/routes/trades.py:367` passes RAW `current_equity`, unfloored).
**That existing divergence is flagged, not fixed** — it is a `swing/web/routes/trades.py` behaviour change
outside this arc's scope, and the form states which figure it used so the operator is never guessing.

`risk_policy_id` comes from the ACTIVE policy row (`swing/data/repos/risk_policy.py`), recorded for provenance.
The RATE fed to `compute_shares` stays `cfg.risk.max_risk_pct` — the same source every other sizing caller
uses; recording the policy id alongside it is what makes a future cfg-vs-policy divergence visible in the
ledger rather than invisible. (`swing/cli.py:170` already ships a divergence warning for the floor; the same
class.)

### D.3 What the form RENDERS (the D25 lesson, made concrete)

Every number appears with the inputs that produced it, on the card, not behind a disclosure:

```
PREPARED ORDER  (LOG ONLY - nothing is sent to the broker)
  BUY 9 FTRE   LIMIT 18.89   GOOD_TILL_CANCEL

  Limit  18.89  = latched pivot 18.34 x 1.03 (zone cap)
  Stop   none   = the last close 19.20 (dated 2026-07-29) is at or above the
                  latched pivot 18.34, so the mandate is a resting BUY LIMIT;
                  a buy stop-limit at 18.34 would sit below the market and be
                  rejected by the broker.
  Pivot  18.34  frozen at the fire: evaluation run 121, session 2026-07-20,
                candidate 11261 (the CURRENT candidates row for FTRE says
                20.19 - this mandate does NOT follow it).
  Qty    9      = floor($37.50 / $4.01)
                  risk per share 4.01 = limit 18.89 - fire-time stop 14.88
                  max risk $37.50 = sizing equity $7,500.00 x 0.500%
                  sizing equity $7,500.00 = max(real equity $1,2xx.xx,
                    risk_equity_floor $7,500.00)
                  risk_policy id 5 (max_account_risk_per_trade_pct 0.5)
                  position cap would allow 59 sh ($1,125.00 / 18.89) - RISK BINDS
                  NOTE: the nightly briefing sized this fire at 10 sh off the
                  PIVOT; this form sizes off the LIMIT so a fill at the cap
                  cannot breach the risk cap.
  Invalidation 14.88 (stop level only - structural base-break is not in V1)

  [ ACCEPT - log this order ]   [ DECLINE ]   reason: [__________________]
```

**THIS SAMPLE IS THE OFFERED STATE AND IT DOES NOT EXIST ON TODAY'S SUBSTRATE (Codex R8 MAJOR 3).** The plan's
first draft stamped this close `2026-07-28`, which is a date FTRE has no close for — the live newest close is
19.20 dated **2026-07-27** while the current derivation session is **2026-07-28**, which is precisely why the
form is WITHHELD right now (§B.3). Writing the derivation-session date onto a close that does not carry it is
the run-level-stamp error (#30) committed inside a plan whose sibling arc exists to fix it, and it would have
propagated into a fixture. So: the sample shows a close dated **2026-07-29**, i.e. the state after the next
nightly (or after the §L State-B seed), and the plan says so here rather than implying today's panel renders
it. **Every FTRE fixture states which close date it seeds and why**; a fixture that quietly uses the
derivation session as the close date FAILS review.

**When the form is WITHHELD** (`PreparedOrderResult.order is None`) the same block renders the mandate facts
plus `withheld_detail`, and **there is no ACCEPT button in the DOM at all** — a
disabled-looking button that posts is worse than no button. A test asserts the ACCEPT control is absent from
the rendered HTML in every withheld case.

### D.4 The delta — `compute_order_delta(framework, actual) -> OrderDelta`

Per-field, at DISPLAY precision (the price-precision-parity gotcha: `round(a, 2) != round(b, 2)`, never a raw
float compare):

```python
@dataclass(frozen=True)
class OrderDelta:
    order_type_differs: bool | None      # None = one side unknown; NEVER False
    duration_differs: bool | None
    # THE STOP LEG IS TRI-STATE, NOT float|None (Codex R6 MAJOR 4). With a bare
    # float|None, "both sides correctly have no stop leg" (the PULLBACK regime's
    # RIGHT answer) and "one side is unknown" both collapse to None -- so a
    # legitimate exact match would be reported as unknown, and unknown is never
    # agreement, so the correct order would be scored as a non-match.
    stop_leg: str                        # both_absent | compared | unknown
    stop_price_delta: float | None       # set IFF stop_leg == 'compared', at 2dp
    limit_price_delta: float | None
    quantity_delta: int | None
    any_difference: bool | None          # None when ANY field is unknown
    unknown_fields: tuple[str, ...]
```

**DURATIONS ARE CANONICALISED BEFORE COMPARISON, NOT COMPARED RAW (Codex R19 MAJOR 8).**
`canonical_duration(raw) -> str` maps the broker's rendering onto the framework's vocabulary
(`GTC`/`GOOD_TILL_CANCEL`/`GOOD_TILL_CANCELLED` -> `GOOD_TILL_CANCEL`; unmapped -> `UNKNOWN`), and the
CANONICAL form is what is PERSISTED into `actual_duration` and what `duration_differs` compares. Comparing raw
strings would report `GTC` vs `GOOD_TILL_CANCEL` as a duration divergence on a semantically identical order —
a manufactured mismatch in the exact metric the ledger exists to compute, and the mirror image of the R17
CRITICAL (there the instrument could not see a real divergence; here it would invent a fake one). A parity
test asserts `GTC` and `GOOD_TILL_CANCEL` compare EQUAL, and that an unmapped duration canonicalises to
`UNKNOWN` and therefore compares as UNKNOWN — never as agreement.

`stop_leg` values: **`both_absent`** — framework and actual both carry no stop leg; this is a MATCH and
contributes False to `any_difference`. **`compared`** — both carry one; `stop_price_delta` holds
`actual - framework` at 2dp. **`unknown`** — exactly one side carries one, or the actual side is not observed
at all; contributes `None`, and `None` is never agreement (the rule 21-A's `_agreement_word` already
enforces). `__post_init__` pins `stop_price_delta is not None` iff `stop_leg == 'compared'`.

---

## E. Classification — `swing/latches/classification.py` (B2, PURE)

```python
LATCH_DISPOSITIONS = frozenset({
    "pre_telemetry", "telemetry_unhealthy",
    "away_unseen", "accepted", "declined", "attested_acted_manually",
    "attested_chose_not_to_act", "attested_was_away", "discipline_lapse",
    "pending_live", "never_actionable",
})
# ELEVEN. `partial_telemetry_unresolved` was drafted and then DELETED by RD ruling 2
# (2026-07-28): partial-coverage-with-no-view collapses into `pre_telemetry`,
# because the REASON is the same in both cases -- the instrument was not there --
# and a second name would imply a distinction the evidence does not support.
#
# A `pending_attestation` state was ALSO drafted and DELETED
# (Codex R3 MAJOR 1): distinguishing "the prompt has been shown" from "it has
# not" would require a persisted prompt-shown bit that nothing writes, so the
# branch was uncomputable from the classifier's pure inputs and would have been
# filled by a hidden heuristic. Collapsing it is also the SEMANTICALLY correct
# answer -- see E.1.

def classify_latch(*, latch, views, intents, telemetry_health,
                   counted_surfaces=ACTIONABLE_VIEW_SURFACES,
                   epoch=LATCH_TELEMETRY_EPOCH_SESSION) -> LatchDisposition
```

### E.0 RD's coverage table is encoded AS A TABLE (his explicit requirement)

The §A.1.1 ruling is a four-row lookup and is implemented as one, **not as nested conditionals** — nested
branches are how a ruled table drifts silently under later edits, which is the exact failure this plan has
been fighting elsewhere (a prose invariant survived three review rounds while the DDL contradicted it, §C.2).

```python
CoverageKey = tuple[str, bool]   # (coverage, awareness_established)
#   coverage              in {"full", "partial", "none"}
#   awareness_established = at least one view row on a COUNTED surface inside
#                           the COVERED portion of the armed window --
#                           REGARDLESS OF ACTIONABILITY.
#
# THE TWO AXES ARE SEPARATE, AND CONFLATING THEM MIS-IMPLEMENTS THE RULING
# (Codex R18 MAJOR 2). RD's table turns on "a view RECORD in the covered
# portion". A withheld-but-recorded view IS such a record: the instrument
# existed and it observed. Requiring actionability HERE would classify that
# latch `pre_telemetry` -- asserting the apparatus was ABSENT when it was
# present and working -- the precise conflation ruling 1 forbids. Actionability
# decides a DIFFERENT question one rung later: given that he looked, was he
# shown a decision (-> discipline_lapse) or not (-> never_actionable).
# Coverage answers "can we know?"; actionability answers "what was he shown?".

RD_COVERAGE_TABLE: dict[CoverageKey, str] = {   # values: a DISPOSITION or _CLASSIFY_NORMALLY
    ("full",    True):  _CLASSIFY_NORMALLY,   # accepted / declined / away / lapse
    ("full",    False): _CLASSIFY_NORMALLY,   # -> away_unseen or never_actionable
    ("partial", True):  _CLASSIFY_NORMALLY,   # awareness ESTABLISHED - classify on it
    ("partial", False): "pre_telemetry",      # cannot distinguish away from dark
    ("none",    True):  "pre_telemetry",      # unreachable (no covered portion can
                                              # hold a record); present so the table
                                              # is TOTAL over the key space
    ("none",    False): "pre_telemetry",
}
```

**THE TABLE IS THE ONLY PLACE COVERAGE IS DECIDED.** `resolve_coverage(...)` returns a frozen
`CoverageVerdict(coverage, awareness_established, table_disposition)` and the §E rungs CONSUME it: no rung
re-derives the epoch, the uncovered window or full-vs-partial, and no rung re-applies a coverage veto after
the table has routed to `_CLASSIFY_NORMALLY`. A latch the table routes normally is classified on awareness and
actionability alone.

Three properties, each with its own test:

1. **TOTALITY.** A test enumerates the full `{full, partial, none} x {True, False}` product and asserts every
   key is present — an unhandled combination cannot fall through to a default.
2. **THE MONOTONE PROPERTY (RD ruling 2's defining consequence).** For every key, flipping
   `awareness_established` `False -> True` never yields `away_unseen`. **Tested THROUGH `classify_latch` on
   concrete substrates, NOT over the table's values (Codex R19 MAJOR 5).** Most table values are the
   `_CLASSIFY_NORMALLY` sentinel, so a table-level assertion proves nothing about the FINAL disposition — a
   broken `_CLASSIFY_NORMALLY` could still return the forbidden negative inference and pass. The test builds
   full / partial / none substrates with actionable and withheld view rows and asserts the dispositions
   `classify_latch` actually emits.
3. **NO RE-DERIVATION.** `classify_latch` calls `resolve_coverage` exactly once and consumes the returned
   `CoverageVerdict`. The test is a BEHAVIOURAL one over representative substrates (does the classifier's
   output depend on anything the verdict does not carry?), **not a source-text search for the absence of
   branches** — the draft's source-text form was unsatisfiable against rungs that legitimately branch on the
   verdict's own fields, and a test that cannot pass gets watered down until it stops detecting drift.

`_CLASSIFY_NORMALLY` hands off to the §E rungs; the table decides only whether the coverage question is
answerable at all.

**TWO AXES, NOT ONE (Codex R1 MAJOR 3).** `LatchDisposition` answers *what did the operator DECIDE*.
It does **NOT** answer *did the order actually work*. Collapsing them would let a broker-REJECTED placement
classify as a clean `accepted` and contribute to the agreement rate — which is the FTRE failure mode itself
(a stop-limit placed above the market and rejected), so a ledger built to measure that failure must not be
able to hide it. `LatchDisposition` therefore carries BOTH:

```python
disposition: str            # the DECISION axis -- LATCH_DISPOSITIONS
execution_outcome: str      # the EXECUTION axis -- accepted_by_broker | rejected_by_broker
                            # | not_submitted | unknown | not_applicable
```

**`execution_outcome` HAS ONE CANONICAL RESOLVER WITH AN EXPLICIT PRECEDENCE (Codex R10 MAJOR 2 — the draft
split it between "validity rows only" here and a fill short-circuit in the prose, which is two sources for one
fact):**

```
resolve_execution_outcome(latch, governing_place_intent, validity_rows) ->
  1. no governing place intent                       -> 'not_applicable'
  2. this place intent IS the latch's LATEST place intent
     AND latch.clear_reason == 'fill'
     AND the fill's session is at-or-after this intent's action_session_date
                                                      -> 'accepted_by_broker'
  3. the LATEST validity row by (recorded_ts, intent_id) WHOSE
     validated_place_intent_id IS that place intent   -> its validity_outcome
  4. otherwise                                        -> 'unknown'
```

**Rung 2 above rung 3 is deliberate: a FILL is authoritative over an attestation.** An order that filled was
self-evidently accepted, the fill is a real position in the trades ledger rather than a recollection, and if
the operator ever mis-attests `not_submitted` on an order that demonstrably filled, the ledger should believe
the position.

**But rung 2 is PARENT-SCOPED, not latch-scoped (Codex R14 MAJOR 2).** A latch may carry several
place/validity cycles — he places, it is rejected, he re-places — and a latch-scoped fill rung would let the
SECOND cycle's fill vouch for the FIRST cycle's rejected order, silently rewriting an execution-parity result
that had been correctly recorded as a failure. So the fill vouches for the **LATEST place intent ONLY**; every
earlier place intent resolves from its OWN validity child or stays `unknown`. Two guards, not one: the
latest-intent test bounds it FORWARD (an earlier cycle cannot borrow a later fill) and the date test bounds it
BACKWARD (an older fill from a prior cycle cannot vouch for a newer intent).

`latch.clear_reason` is an input the classifier ALREADY receives — this is a named field on a value object,
not a hidden `trades` read, and §E.1's fill short-circuit is the same rung 2 seen from the UI side (it is why
no prompt renders). Rung 3 is per-parent and takes the LATEST within that parent — never "the latest validity
row for this latch", which would let a second place/validity cycle retroactively rewrite the first one's
reported outcome (R4 MAJOR 3). A test asserts a mis-attested `not_submitted` on a FILLED latch still resolves
`accepted_by_broker`, and that a fill dated BEFORE the place intent does not.

**HOW A `validity` ROW GETS WRITTEN — the flow the plan first omitted (Codex R3 MAJOR 3).** There is a real
observable signal even though this arc places nothing, and it is exactly the one the brief calls "the FTRE
broker-rejection class for free":

**WHERE THE PROMPT LIVES, since only one surface can answer the question (Codex R8 MAJOR 1).** The
presence/absence branch needs the LIVE broker book, and the intent path is forbidden from borrowing the Schwab
client at all (the Global Constraints zero-`borrow` seam assertion). So the validity prompt is rendered by
**`POST /latches/orders`** — the fragment that ALREADY reads the order book, already owns the borrow, and
already holds the resting-order set the presence test needs. `GET /latches` renders no validity prompt (it has
no broker knowledge and must not acquire any — A4), and `POST /latches/intent` merely RECORDS the answer the
fragment offered, carrying the observed `order_id` as a hidden anchor exactly like every other hidden field
(§G.2).

**And a THIRD branch, `broker_unavailable`:** when `resolution.kind != "ok"` (sandbox, unconfigured, client
absent, read failed) the order book is UNKNOWN, so **NO validity prompt renders at all** — neither presence nor
absence is knowable, and offering a prompt built on an unknown book would invite an answer the operator would
reasonably infer from the panel's own silence. This matches 21-A's existing posture exactly: an unknown order
book fires nothing.

**The prompt fires in BOTH directions, and that is not symmetry for its own sake (Codex R5 CRITICAL).** A
first draft fired the prompt only on ABSENCE. That leaves the POSITIVE case — an order the broker plainly
accepted — permanently `unknown`, so §F.3's agreement NUMERATOR (which requires
`execution_outcome == 'accepted_by_broker'`) could never be populated by anything: the report would measure
only failures and report a permanently empty success rate. So:

- **PRESENCE branch — gated on an EXACTLY-ONE match (Codex R9 MAJOR 3).** A `place` intent whose framework
  params MATCH a currently-resting broker order (at display precision, the same comparison §D.4 uses) renders:
  *"Your logged LIMIT 18.89 / 9 sh order for FTRE is resting at the broker as order `<id>`. Confirm?"* with
  **`accepted_by_broker` pre-selected** and the observed `order_id` carried into `actual_broker_order_id`.
  **It renders ONLY when exactly ONE resting BUY order is attributable to this latch and `join.indeterminate`
  is False.** With two attributable orders there is no unique `order_id` and the chosen one would be
  arbitrary; with an indeterminate status the broker's own answer is unknown. In both cases the fragment
  renders the multiplicity / indeterminate note 21-A already ships and **no validity prompt**.

  **"Attributable" means matched to the LATCH, NOT to the framework order's exact params (Codex R17
  CRITICAL — the most consequential finding of the chain).** The first draft gated on an exact framework-params
  match, which silently excluded the ONE case the ledger exists to measure: FTRE's actual resting order is
  `LIMIT 18.89 / 10 sh` against a framework `LIMIT 18.89 / 9 sh`, so under an exact-match gate no prompt would
  ever fire, `validity` rows could carry no `actual_*` params, the `place` row is append-only — and the +1
  quantity delta, **the arc's own worked example**, could never reach the ledger. The instrument would have
  been able to record agreements and never a DIVERGENCE, which is the one thing it is for. So the prompt fires
  on 21-A's existing latch attribution (`_match_latch`, frozen-price based) and **PRE-FILLS THE OBSERVED
  PARAMS INTO THE `actual_*` FIELDS whether or not they match**. When they match, `accepted_by_broker` is
  pre-selected as before; when they DIVERGE the prompt says so — *"this order differs from the prepared one
  (quantity 10 vs 9); confirming records BOTH sides"* — which is the honest presentation of a divergence and
  the moment the parity metric actually gets its data.

  **BOTH presence sub-cases submit `validity_outcome='accepted_by_broker'` (Codex R19 MAJOR 7).** A resting
  broker order is positive acceptance evidence *whether or not its quantity matches* — the broker accepted an
  order; the operator simply placed a different one from the prepared one. If the divergent row landed
  `unknown` instead, FTRE's delta would be visible in the ledger and yet EXCLUDED from the agreement
  denominator (§F.3 requires `accepted_by_broker` there), so the arc's own worked example would still not
  reach the metric it exists to feed — the R17 CRITICAL surviving one layer further out. Task 7 asserts the
  divergent FTRE row ENTERS the agreement denominator and FAILS the numerator via `quantity_delta`, which is
  precisely what "the agreement rate" is supposed to mean.
- **FILL SHORT-CIRCUIT — the prompt does not fire at all when the framework already knows.** If the latch's
  own terminal walk cleared it with `clear_reason='fill'` (21-A §A.6, derived from `trades`), the order was
  self-evidently accepted: `execution_outcome` is derived as `accepted_by_broker` from the FILL, with no
  prompt and no `validity` row. This is the one place the framework may answer for itself, because the
  evidence is a real position in the ledger rather than an absence.
- **ABSENCE branch** (only for a latch NOT cleared by fill). A `place` intent from an EARLIER session with
  **no** matching resting order renders: *"You logged a LIMIT 18.89 / 9 sh order for FTRE on 2026-07-29. No
  matching resting order is visible at the broker. Was it rejected, never submitted, or do you not know?"*
  with **nothing pre-selected**. **"Filled" is deliberately NOT an option** (Codex R7 MAJOR 2): it is not in
  `LATCH_VALIDITY_OUTCOMES`, so offering it would force the handler to mislabel or discard the answer — and
  it does not need to be offered, because the fill short-circuit above already covers that case from data the
  framework owns. The three offered answers map exactly onto `rejected_by_broker` / `not_submitted` /
  `unknown`; a test pins that the rendered prompt's option set EQUALS the enum minus `accepted_by_broker`.
- **The asymmetry survives, and it is what makes the two branches differ.** PRESENCE is direct positive
  evidence — the order is visibly there — so the framework may pre-select the answer. ABSENCE is consistent
  with a fill, a rejection, a cancel AND a never-submitted order, so the framework may raise the QUESTION and
  may NOT pre-select an ANSWER. That is exactly *you may raise a mismatch alarm but you may not assert a
  match*, applied to an execution outcome instead of an order shape.
- **The framework NEVER WRITES either answer unattended.** Both branches require the operator's click, and
  `unknown` persists until he clicks. Pre-selection is a convenience on the presence branch; it is not an
  assertion, and a test asserts no `validity` row is ever written without a POST.
- **THE BROKER SNAPSHOT IS ANCHORED AND AGE-BOUNDED (Codex R9 MAJOR 1, accepted in its STALENESS half).** The
  fragment emits **ONE canonical hidden field, `broker_snapshot_json`** (Codex R20 MAJOR — the draft named
  two hidden fields while `validity_detail` required the full envelope, and `POST /latches/intent` is
  forbidden from borrowing Schwab so it could not reconstruct the missing keys at submit time; the audit row
  was therefore either unwritable or populated from guesses). The envelope carries EXACTLY the keys in
  `LATCH_BROKER_SNAPSHOT_KEYS` (§C.2's `json_remove` path list is the roster; no site states a count) — `broker_snapshot_ts` (SERVER-stamped at fragment
  render), `broker_snapshot_branch` — the FRAGMENT's render vocabulary is three-valued
  (`presence`/`absence`/`unavailable`), but a PERSISTED `validity` row's is two-valued: the schema forbids
  `unavailable` (§C.2, Codex R26 MAJOR), which is not an extra rule but the same one this bullet already
  states — an unavailable book renders no prompt, so no envelope is ever submitted carrying it, and an
  append-only row asserting an outcome against an unknown book must be unwritable rather than merely
  unreachable — `broker_snapshot_digest`,
  `broker_snapshot_session` (the action session the BROKER VIEW came from - distinct from the row's
  `action_session_date`, which is the MANDATE's session, section C.2), `attributable_order_count`,
  `exact_framework_match_count`, `indeterminate`. `broker_snapshot_digest` is itself one of the seven and is
  computed over the broker-book state (§G.1), NOT over the other six keys — the two are separate facts and
  conflating them was how the count drifted. The handler VALIDATES the
  envelope (parseable, every roster key present, correct value shapes — the same 4-tier ladder) and PERSISTS IT VERBATIM
  into `validity_detail`, never synthesising a missing key; a test asserts the fragment's emitted key set
  EQUALS the set `validity_detail` requires, so the two cannot drift. `POST /latches/intent` REFUSES a
  `validity` submission whose snapshot is not from the CURRENT action session or is older than
  `LATCH_BROKER_SNAPSHOT_MAX_AGE_SECONDS` (a named constant, default 900), with `409` + *"this broker view is
  stale; reload to answer against the current order book."* The WHOLE envelope is persisted into
  `validity_detail`, so the row is self-describing about the snapshot it was answering — an audit-grade row
  must carry what it was looking at, or a later reader cannot tell a fresh answer from a day-old tab.
- **The FORGERY half is scoped out, with the reason recorded rather than waved.** Codex's stronger fix is a
  server-signed broker-context token. This app binds `127.0.0.1`, serves a single operator, ships no signing-
  key infrastructure, and already treats `OriginGuardMiddleware` (strict) as its trust boundary; a forged
  local POST implies an attacker who can already run code as the operator, at which point the DB is directly
  writable and the token protects nothing. Introducing key management for that threat is cost without safety.
  **What the staleness bound above DOES buy is the realistic failure — an honest answer about a stale
  view — and that is the one that would actually corrupt the ledger.** The signed token is BANKED (§M) as the
  right move if the app ever leaves localhost, which is exactly when the calculus changes.
- The `filled` answer is cross-checkable: the latch's own terminal walk independently detects a fill from
  `trades` (21-A §A.6). A `validity` row claiming `accepted_by_broker` on a latch the derivation cleared as
  `fill` is coherent; one on a latch that expired at horizon is a flag the CLI report prints.
- **V1 honesty, stated where the number is printed (§F.3):** most rows will be `unknown` for a while, because
  the prompt only fires once a `place` intent has aged past its session. The report prints
  `validity_unknown` on the same line as the agreement rate for exactly this reason. Stage 2's
  `preview_order` is what makes validity automatic — and eliminates the class. **`unknown` is not agreement** — the same rule 21-A's `_agreement_word` already enforces. §F.3's
agreement rate excludes `rejected_by_broker` and `not_submitted` from the numerator and reports
`validity_unknown` as its own visible count rather than folding it in either direction.

**ONE ORDERING RULE, STATED ONCE, BEFORE THE RUNGS (Codex R27 MAJOR).** `latch_order_intents` is
append-only, so a latch can legitimately accumulate SEVERAL intents of the same kind — including two `attest`
rows carrying DIFFERENT `attested_disposition` values (he attests `was_away`, then corrects himself to
`chose_not_to_act`; a correction is a NEW row, which is what append-only requires). The rungs below said
"`intents` contains an `attest`" with no rule for WHICH one, so the disposition depended on the order the
list happened to arrive in — and because `attested_was_away` and `attested_chose_not_to_act` land in
DIFFERENT R buckets (`attested_away_r` vs `decision_r`), a nondeterministic read moves the measurement. This
is the same "latest by what?" gap already ruled twice in this arc (R4 MAJOR 3 on validity parents, R10 MAJOR
2 on the execution resolver), so it takes the same answer rather than a new one:

> **Within each intent KIND, the GOVERNING row is the LATEST by `(recorded_ts, intent_id)`.** The tiebreak on
> `intent_id` is load-bearing — `recorded_ts` is whole seconds, so two rows can share one — and it is the
> same total order §F.3 uses for the report and §E's rung 3 uses for validity children. Earlier rows are
> HISTORY, retained and readable, never silently authoritative.

A test writes two conflicting `attest` rows for one latch and asserts the disposition follows the LATER one
DETERMINISTICALLY, under both list orders (shuffle the input) — an implementation reading "the first attest
found" passes under one order and fails under the other, which is exactly the bug.

**Precedence on the DECISION axis (each rung gets its own discriminating test):**

1. `intents` contains a `place` -> **`accepted`** (the GOVERNING `place` per the rule above; an earlier
   `decline` is history, not the outcome). **This says he DECIDED to place, and nothing more** — a rejected
   order is still an accepted decision, and it is `execution_outcome` that says so. A test asserts a `place` intent with
   `validity_outcome='rejected_by_broker'` yields `accepted` + `rejected_by_broker` and is EXCLUDED from the
   agreement numerator.
2. else `intents` contains a `decline` -> **`declined`** (the GOVERNING `decline`; immaterial today since
   every `decline` yields the same disposition, but stated so the ladder is uniform and a future
   reason-dependent read cannot inherit an unstated order).
3. else `intents` contains an `attest` -> **`attested_<disposition>` OF THE GOVERNING `attest` ROW** — the
   latest by `(recorded_ts, intent_id)`. This is the rung where the ordering rule actually BITES, because the
   attested dispositions differ from each other in R BUCKET, not just in label. `attested_was_away` is a
   THIRD terminal category (§A.1.6 ruling 2): counted in `classifiable_fires`, EXCLUDED from the discipline
   signal, and included in the ATTESTED away rate only — never merged into the objective one, because
   testimony is not telemetry (§A.0). **A CORRECTION MUST WIN, and that is the point of taking the latest:**
   if he attests `was_away` and then corrects to `chose_not_to_act`, the correction moves the fire INTO the
   discipline signal against himself. Taking the earlier row would silently preserve the more flattering
   answer — the one-sided bias §A.1.6 names, arriving through the ordering door instead of the default door.
4. else if `verdict.table_disposition` is a concrete disposition (i.e. NOT `_CLASSIFY_NORMALLY`) -> return it.
   This is the ONLY route to `pre_telemetry`; no rung below re-decides coverage (§E.0).
   **THE COVERAGE TABLE IS CONSUMED BEFORE TELEMETRY HEALTH (Codex R20 MAJOR).** The draft ran health first,
   so a partially-covered latch with no view rows and a dark covered portion returned `telemetry_unhealthy`
   instead of RD's ruled `pre_telemetry` — health PRE-EMPTING the ruling, and falsifying §E.0's own claim that
   the table is the only place coverage is decided. Health is a statement about the INSTRUMENT'S RELIABILITY
   and bears only on a window the table says is ANSWERABLE; where the table has already ruled the question
   unanswerable, a health verdict adds nothing and must not overwrite the reason. A test asserts
   partial/no-awareness with `broken` health STILL returns `pre_telemetry`.

5. else if `telemetry_health.verdict != "ok"` for this latch's covered window ->
   **`telemetry_unhealthy`** (excluded from BOTH the discipline signal and the away rate).
   **`!= "ok"`, NOT `== "broken"` (Codex R18 MAJOR 5).** The draft excluded only `broken`, which let a SHORT
   fully-covered window with NO beacon witness (`indeterminate`: covered = 0, uncovered below the threshold)
   score `away_unseen` and enter the away rate — while the plan's OWN seeded discriminator (T-B) requires
   sibling view rows to prove the beacon was alive before it will call anything away. The classifier must hold
   itself to the standard its test does. `telemetry_unhealthy` carries the verdict so the label distinguishes
   `broken` from `indeterminate` (RD's labelled-reduction coupling, §A.1.1).
6. else if there is at least one view row with **`actionable_ever_viewed = 1`** inside the covered window:
   - latch is LIVE -> **`pending_live`** (no prompt; the mandate can still be acted on). **Reported, never
     scored** (§A.1.6 ruling 1): it enters no denominator, because a latch that has not terminated is not an
     observation yet and its verdict would move as the window runs.
   - latch is TERMINAL -> **`discipline_lapse`**, with `prompt_required=True`. There is no intermediate
     state — see E.1.
7. else (no `actionable_ever_viewed = 1` view row in the covered window) — **coverage is NOT re-tested here;
   reaching this rung already means the table routed to `_CLASSIFY_NORMALLY`**:
   - `verdict.awareness_established` is True (>= 1 view row, necessarily all `actionable_ever_viewed = 0`)
     -> **`never_actionable`** — he looked, and the panel presented no decision. **This is reachable from a
     PARTIALLY-covered window too** (R19 MAJOR 3): the instrument existed and observed, so the honest answer
     is "nothing was shown to him", not "the instrument was absent".
   - `verdict.awareness_established` is False -> **`away_unseen`**. Reachable ONLY from a FULLY covered
     window, because `("partial", False)` and `("none", *)` were already returned by rung 4 as
     `pre_telemetry`.

**THE COVERAGE / ACTIONABILITY RULE, STATED ONCE.** Derived from RD's ruling-2 sentence and from nothing else:

> **partial + NO awareness -> `pre_telemetry`. partial + awareness + no actionable rows -> `never_actionable`.
> FULL + no awareness -> `away_unseen`. FULL + awareness + no actionable rows -> `never_actionable`.**

FTRE is `pre_telemetry` because it has NO view rows at all — not because coverage vetoes actionability.
`never_actionable` is reachable from BOTH full and partial coverage: it says *the instrument was there, it
observed, and what it showed him was nothing actionable*, which is true whenever awareness is established,
regardless of how much of the window was instrumented.

**Why the rung ORDER is what it is.** Rungs 1-3 (explicit operator actions) are ground truth and need no
telemetry. Rung 4 (RD's table) decides whether the coverage question is answerable AT ALL, and nothing may
pre-empt a ruling. Rung 5 (health) therefore bears only on a window the table says IS answerable — a broken
beacon must not be laundered into `away_unseen`. Rungs 6-7 read actionability, a different question from
coverage: coverage answers *can we know?*, actionability answers *what was he shown?*

### E.1 The pessimistic default is load-bearing, and collapsing the prompt state MAKES it structural

A terminal, viewed, unintended, unattested latch is **`discipline_lapse` IMMEDIATELY** — the instant the latch
goes terminal, before any prompt is rendered, and whether or not one ever is. `prompt_required=True` rides on
that disposition: the prompt is shown BECAUSE the cell has already been scored as a lapse, and attesting is the
operator's opportunity to CORRECT it (to `attested_acted_manually` / `attested_chose_not_to_act` /
`attested_was_away`, all of which are rungs 1-3 and therefore beat rung 6).

This is strictly better than the drafted `pending_attestation` intermediate, on two counts:

1. **It is computable.** The intermediate required a persisted "prompt has been shown" bit that nothing writes
   (Codex R3 MAJOR 1). Adding one would mean a second write-on-render seam — the exact thing A4 exists to
   avoid — for no measurement gain.
2. **It is more honest.** An intermediate state makes the pessimistic default DEPEND ON THE INSTRUMENT having
   rendered a prompt: if the operator never opens the panel again after the latch expires, the lapse would sit
   forever in a neutral "pending" bucket and never be scored. That is the instrument flattering its subject
   through inaction, which is the precise failure RD's rule forbids. Scoring at terminal makes the default
   independent of whether he ever comes back.

There is no configuration, no grace window and no "unknown" bucket for this cell. A test asserts that no code
path maps it to `away_unseen`, `pending_live` or any excluded bucket, and that its `effective_disposition` is
`"discipline_lapse"` with zero views of the prompt.

### E.2 Never prompt where telemetry says never-viewed

`prompt_required` is True on **exactly one** disposition: `discipline_lapse`. It is False on `away_unseen`,
`pre_telemetry`, `telemetry_unhealthy`, `never_actionable`, `accepted`,
`declined`, every `attested_*` and `pending_live`. **`never_actionable` is the newest and most important
False**: prompting a man to attest about a decision the panel never presented is the purest form of the
train-the-dismissal-reflex failure. A parametrised test walks **every member of `LATCH_DISPOSITIONS`** (parametrised OVER the frozenset,
never over a copied list, and stating no count) and asserts exactly one
True — so a future disposition added without a decision about its prompt FAILS.
Rationale, recorded because it constrains future change: a prompt on an objectively-resolved cell trains
dismissal, and dismissal is what eventually kills the honest answer on the cell that matters.

### E.3 A "view" for classification means an ACTIONABLE view, ON A COUNTED SURFACE, of THIS latch while it was LIVE

Three conjuncts, each enforced somewhere different:

1. **Actionable** — the row's own `actionable_ever_viewed = 1` (§C.1), and NEVER either of the
   first/last companion columns, which describe individual views rather than the session. NOT a write contract: the withheld
   render is recorded too, as `0`, because the two silences ("he saw nothing actionable" and "he never
   looked") are wrong in OPPOSITE directions and must be told apart. A latch with only `0` rows
   across its whole armed window is **`never_actionable`**, excluded from the discipline signal and from the
   away rate.
2. **On a counted surface** — enforced HERE, explicitly (Codex R2 MAJOR 2). The plan added a `surface` column
   and then never read it, which would mean that the moment 21-F adds a second surface, a non-panel row would
   silently satisfy the panel's "viewed" predicate and move a disposition. So:

   ```python
   # swing/latches/constants.py
   LATCH_VIEW_SURFACES = frozenset({"latch_panel"})       # the schema CHECK enum
   ACTIONABLE_VIEW_SURFACES = frozenset({"latch_panel"})  # which ones COUNT as a view
   ```

   `classify_latch`, `assess_telemetry_health` and the panel's `_load_views` all take
   `counted_surfaces=ACTIONABLE_VIEW_SURFACES` and FILTER on it. **The two frozensets are deliberately
   separate and deliberately equal today.** Adding a surface to the CHECK enum is a schema decision; adding it
   to `ACTIONABLE_VIEW_SURFACES` is a MEASUREMENT decision and RD's (it is exactly the 21-F §4 question —
   *does a dashboard glance count evidentially as a view?*). Keeping them separate means a future surface
   cannot change the away/lapse math as a side effect of being added.

   Regression tests, **exercised through the `counted_surfaces=` PARAMETER rather than by planting an invalid
   surface row (Codex R20 MAJOR)**: today `LATCH_VIEW_SURFACES == ACTIONABLE_VIEW_SURFACES == {"latch_panel"}`
   and both the SQL CHECK and the model validator reject any other value, so a test planting a `dashboard` row
   could only pass by BYPASSING the very #11 mirror it exists to respect. Instead the PURE classifier and
   health calls are invoked with `counted_surfaces=frozenset()` over a valid `latch_panel` row and must ignore
   it — same property, no invalid fixture. Real non-counted-surface behaviour is tested when 21-F widens the
   enum.
   A test also asserts `ACTIONABLE_VIEW_SURFACES <= LATCH_VIEW_SURFACES` (an uncounted-but-unwritable surface
   is a typo, not a design).
3. **While LIVE** — `view_session_date` falls inside the latch's live window AND `latch_state_at_first_view`
   is a LIVE state (`armed` / `order_resting`). A view recorded of a `filled` latch is not evidence about a
   decision window that had already closed. `latch_view_events` records the state at view time precisely so
   this is a read, not a re-derivation against a world that has since changed (21-A §C.1).

---

## F. Telemetry health + the away rate (B5)

### F.1 `assess_telemetry_health(...) -> TelemetryHealth` — PURE

Over a session window, and per latch for rung 4 of §E:

| counter | definition |
|---|---|
| `uninstrumented_sessions` | sessions before `LATCH_TELEMETRY_EPOCH_SESSION`. Excluded from BOTH counts below — not "uncovered", *uninstrumented*. |
| `covered_sessions` | instrumented sessions on which >= 1 live latch existed AND >= 1 view row exists on a COUNTED surface (`ACTIONABLE_VIEW_SURFACES`), for ANY latch, of EITHER `actionable` value |
| `uncovered_sessions` | instrumented sessions on which >= 1 live latch existed AND ZERO such rows exist |

**The two filters are deliberately different and the difference is not an oversight (Codex R8 MAJOR 2 — the
first draft stated the rule two different ways in §E.3 and here, which is worse than either rule).** SURFACE
filters BOTH counters: the health check is asking whether *the beacon we measure from* fired, so a row on an
uncounted surface tells us nothing about it. `actionable` filters NEITHER: a row of either value proves the
beacon fired, which is the only question this check asks. The regression test asserts exactly this pair — an
uncounted-surface row does NOT create a covered session; a fully-withheld row on a counted surface DOES.

**Verdict — the DARK count binds regardless of `covered` (Codex R19 MAJOR 6):**
- `uncovered >= LATCH_TELEMETRY_DARK_SESSIONS_THRESHOLD` -> **`broken`**, *even when `covered > 0`*. The draft
  keyed `broken` on `covered == 0`, so a 30-session window with ONE sibling view and 29 dark sessions verdicted
  `ok` and could hand `away_unseen` to the away rate — manufacturing away-rate evidence out of an instrument
  that was dark for 97% of the window. One beacon hit proves the beacon existed once; it does not make the
  window observed. (Threshold is a named constant, default 5, so a genuinely quiet week does not trip it.)
- `covered == 0 and 0 < uncovered < threshold` -> **`indeterminate`**.
- otherwise -> **`ok`**, carrying the three counters.

A test plants `covered = 1, uncovered >= threshold` and asserts `broken` — under the draft's rule that
substrate verdicts `ok` and the latch reaches `away_unseen`, so the test discriminates.

**Honest about what it cannot do:** this check cannot distinguish "beacon broken" from "operator away for the
whole window" — and it does not claim to. It identifies the SHAPE and refuses the number. The stronger check
(an independent witness that the panel was rendered) is **investigated and rejected for V1** with its reason
recorded: `POST /latches/orders` does write a `schwab_api_calls` audit row on every panel render, but it is
stamped `surface="trade_entry"` (`swing/web/view_models/latches.py:682`), which the trade-entry auto-fill also
writes — so it cannot attribute a render to the panel. Banked as V2: a dedicated audit surface value would make
this check two-sided. **Recording the limitation is the requirement; over-claiming would be the failure.**

### F.2 The away rate cannot be obtained without its verdict

```python
@dataclass(frozen=True)
class AwayRateResult:
    # TWO RATES OVER ONE DENOMINATOR (RD ruling 2, section A.1.6). Same
    # denominator is what makes them comparable and what makes the second an
    # UPPER BOUND on the first rather than a different statistic.
    objective_rate: float | None   # away_unseen / classifiable -- PRIMARY
    attested_rate: float | None    # (away_unseen + attested_was_away) / classifiable
                                   #   -- the explicit UPPER BOUND
    away_unseen_fires: int
    attested_was_away_fires: int
    # THE DENOMINATOR: TERMINAL, CLASSIFIABLE observations only (RD ruling 1).
    # Excludes pending_live (not an observation yet), and excludes
    # pre_telemetry / never_actionable / telemetry_unhealthy (unattributable).
    classifiable_fires: int
    pending_fires: int             # REPORTED, never scored -- so the reader sees
                                   # the pipeline rather than a silently smaller corpus
    excluded_fires: int
    health: TelemetryHealth        # NOT optional, NOT defaulted
    withheld_reason: str | None
```

Both rates are `None` when `health.verdict == "broken"` — the gate applies to the pair, since an unreliable
beacon corrupts the objective numerator directly and the bound derived from it consequently. There is no
function anywhere that returns a bare float away rate; `health` is a required constructor argument, so a caller
cannot obtain either number without the verdict travelling with it. A test constructs the `broken` substrate
and asserts BOTH rates are `None` and `withheld_reason` names the counters.

**STAGE-3 READS THE OBJECTIVE RATE AS PRIMARY, THE ATTESTED RATE AS AN UPPER BOUND (RD ruling 2).** The CLI
report (§ Task 9) prints them on adjacent lines with exactly those labels, so the decision that would automate
the operator's entries cannot quietly be taken on the larger number. A test asserts the rendered report
contains both labels and that the attested rate is `>=` the objective rate whenever both are non-`None`.

### F.3 The three R buckets (A.1.2)

**THE THREE R BUCKETS ARE A PARTITION, COMPUTED BY ONE FUNCTION (Codex R10 CRITICAL).** The draft described
the buckets in two places — §A.1.5's (now-deleted) branch seam moved `pre_telemetry` into
`away_r`, while this section still said `unattributable_r` absorbed them — so the same fire
could land in two buckets, or the seam could be silently ignored, and neither the away rate nor the bucket
totals would be trustworthy. There is now exactly ONE mapping:

```python
def r_bucket_for(disposition: str, *, is_terminal: bool) -> str:
    """EXACTLY ONE bucket, and NO DEFAULT (section A.1.6).

    `is_terminal` IS REQUIRED AND IT GATES EVERYTHING (R23 CRITICAL). RD's
    ruling 1 is "rates compute over TERMINAL, classifiable observations only",
    and a disposition-ONLY function cannot enforce that: `pending_live` is
    reached at rung 6 only for a LIVE latch that HAS actionable views and NO
    intent, so a live latch with a `place` intent scores `accepted` ->
    decision_r, a live latch with no views scores `away_unseen` -> away_r, and a
    live latch with withheld-only views scores `never_actionable`. All three are
    non-terminal observations entering scored buckets -- the exact corruption
    ruling 1 forbids, and it slipped in because the ruling was encoded as a
    disposition rather than as a GATE.

    The buckets in `R_BUCKETS` PARTITION the corpus: every (disposition, is_terminal) pair
    lands in exactly one and the five sums reconcile to the total. A trailing
    `return "decision_r"` would make that true while silently ASSIGNING any
    disposition nobody ruled on -- which is how `pending_live` and
    `attested_was_away` ended up scored as operator judgment without a ruling.
    So membership is explicit in all five directions and an unlisted disposition
    RAISES.

    RD singled this guard out as worth more than either ruling it produced,
    because the next unlisted disposition will be one nobody has thought of.
    DO NOT reintroduce a default.
    """
    # MEMBERSHIP FIRST -- THE TERMINALITY GATE IS A DEFAULT IN DISGUISE UNLESS
    # IT IS (Codex R25 MAJOR). The R24 ordering ran the gate BEFORE the
    # membership ladder, so an unlisted disposition with is_terminal=False
    # returned "pending_r" and was silently absorbed -- the very thing the
    # trailing `return "decision_r"` was deleted for, relocated rather than
    # removed. It also read as deliberate: Task 5 had noticed the hole and
    # worked AROUND it by only testing the terminal call. A guard whose test is
    # shaped to avoid the case it misses is not a guard.
    #
    # THE CHECK IS AGAINST THE RULED UNION, **NOT** AGAINST LATCH_DISPOSITIONS.
    # Membership in LATCH_DISPOSITIONS only says the CLASSIFIER can emit it; it
    # says nothing about anyone having ruled its bucket, and a disposition added
    # to the enum without a ruling is the exact case A.1.6 exists for. Checking
    # the enum would let that one straight through the gate into pending_r.
    if disposition not in _RULED_DISPOSITIONS:
        raise ValueError(
            f"{disposition!r} has no ruled R bucket; see plan section A.1.6")
    # COHERENCE SECOND (R24 MAJOR). `pending_live` means "the latch is LIVE", so
    # (pending_live, is_terminal=True) is not a state the classifier can
    # legitimately produce -- and silently bucketing it as pending would hide a
    # classifier bug in the very report layer built to stop silent absorption.
    if disposition in PENDING_DISPOSITIONS and is_terminal:
        raise ValueError(
            "incoherent cell: pending_live with is_terminal=True")
    # RULING 1, ENFORCED AS A GATE: a latch that has not terminated is not an
    # observation yet, WHATEVER its current display disposition says. Reached
    # only for a KNOWN disposition, so it can no longer absorb an unruled one.
    if not is_terminal:
        return "pending_r"
    if disposition in AWAY_RATE_COUNTED_DISPOSITIONS:   # telemetry-derived
        return "away_r"
    if disposition in ATTESTED_AWAY_DISPOSITIONS:       # ruling 2: testimony,
        return "attested_away_r"                        # not telemetry
    if disposition in UNATTRIBUTABLE_DISPOSITIONS:      # the REMAINDER of the
        return "unattributable_r"                       # excluded set
    if disposition in DECISION_DISPOSITIONS:
        return "decision_r"
    # UNREACHABLE while _RULED_DISPOSITIONS is the union of the five sets --
    # kept because a defence that depends on another defence still holding is
    # not a defence (the same reasoning as the C.2 trigger belt).
    raise ValueError(
        f"{disposition!r} has no ruled R bucket; see plan section A.1.6")

_ALL_EXCLUDED_DISPOSITIONS = frozenset({
    "away_unseen", "pre_telemetry",
    "never_actionable", "telemetry_unhealthy",
})
PENDING_DISPOSITIONS       = frozenset({"pending_live"})
ATTESTED_AWAY_DISPOSITIONS = frozenset({"attested_was_away"})
# EXECUTABLE, NOT A COMMENT (Codex R26 MAJOR). This was left commented out as a
# pointer to A.1.5, while r_bucket_for, UNATTRIBUTABLE_DISPOSITIONS and
# _RULED_DISPOSITIONS all USE it -- so the block copied literally raised
# NameError at import. The same class as the R23 MINOR two lines down. A block
# an implementer is told to follow has to RUN.
AWAY_RATE_COUNTED_DISPOSITIONS = frozenset({"away_unseen"})   # fixed at A.1.5

# WRITTEN OUT EXPLICITLY, not derived as "everything left over". Codex R23
# noted the partition is total/disjoint ONLY IF this set is exactly these five,
# and the constant was USED by r_bucket_for while being defined NOWHERE -- the
# same copy-it-literally-and-get-a-NameError class as the R23 MINOR one line
# up. It is NOT derived by subtraction on purpose: `decision_r` is the bucket a
# missing ruling would silently fall into, so it must be the one set that can
# only grow by someone TYPING a disposition into it.
DECISION_DISPOSITIONS = frozenset({
    "accepted", "declined",
    "attested_acted_manually", "attested_chose_not_to_act",
    "discipline_lapse",
})

UNATTRIBUTABLE_DISPOSITIONS = (
    _ALL_EXCLUDED_DISPOSITIONS
    - AWAY_RATE_COUNTED_DISPOSITIONS
    - ATTESTED_AWAY_DISPOSITIONS
)

# THE RULED UNION -- what `r_bucket_for` validates membership against, and the
# reason the terminality gate can no longer absorb an unruled disposition.
_RULED_DISPOSITIONS = (
    AWAY_RATE_COUNTED_DISPOSITIONS | ATTESTED_AWAY_DISPOSITIONS
    | UNATTRIBUTABLE_DISPOSITIONS | DECISION_DISPOSITIONS
    | PENDING_DISPOSITIONS
)

# THE BUCKET ROSTER -- the closed set of values r_bucket_for can RETURN, named
# so that no site has to say "the five buckets". `ExecutionParityReport` builds
# its per-bucket fields by ITERATING this, the partition test iterates it, and
# the CLI report prints it -- so a sixth bucket added to the resolver cannot be
# silently omitted from any of the three. A test asserts the set of values
# r_bucket_for actually returns over the whole coherent cell product EQUALS
# R_BUCKETS, which is what keeps the roster honest rather than aspirational.
R_BUCKETS = frozenset({
    "decision_r", "away_r", "attested_away_r", "unattributable_r", "pending_r",
})
```

**`_ALL_EXCLUDED_DISPOSITIONS` is defined ABOVE its use** (R23 MINOR — the draft's constant order raised
`NameError` if copied literally), and `ATTESTED_AWAY_DISPOSITIONS` is subtracted too, or `away_unseen`'s
sibling would fall into `unattributable_r` as well as its own bucket.

**`_RULED_DISPOSITIONS` MUST EQUAL `LATCH_DISPOSITIONS`, and that equality is its own test — but it is the
CONCLUSION, never the CHECK.** Validating membership against `LATCH_DISPOSITIONS` would be the same hole one
step out: the enum says only that the CLASSIFIER may emit a value, not that anyone RULED its bucket, so a
disposition added to the enum without a ruling would pass the guard and fall through the terminality gate
into `pending_r` — silently scored as "not an observation yet" rather than raising. Validating against the
UNION OF THE FIVE SETS means a new disposition is unbucketable until someone adds it to one of them, which is
the deliberate act with a reviewer that §A.1.6 asks for. The equality test then catches the reverse omission
(a set member that is not a legal disposition — a typo, not a design).

`UNATTRIBUTABLE_DISPOSITIONS` is DERIVED by set subtraction, never hand-written — that is what makes the
overlap unrepresentable rather than merely tested-against.

**THE PARTITION IS OVER CELLS, NOT OVER DISPOSITIONS (R24 MAJOR).** Since the terminality gate landed, a
disposition no longer HAS one bucket: `accepted` is `decision_r` when terminal and `pending_r` when not. A
set-membership assertion phrased as *"every member of `LATCH_DISPOSITIONS` appears in exactly one of the five
sets"* is therefore either false or silently testing the pre-gate model. The invariant is:

- every **COHERENT** `(disposition, is_terminal)` cell maps to exactly one bucket;
- the **INCOHERENT** cell `(pending_live, True)` RAISES;
- `r_bucket_for` RAISES on a disposition absent from all five sets — so a future disposition cannot be
  absorbed into `decision_r` by a default (§A.1.6);
- `decision_r + away_r + attested_away_r + unattributable_r + pending_r` equals the corpus total.

No assertion may claim a disposition belongs to exactly one RUNTIME bucket independent of terminality.

**THE BLOCK ABOVE WAS EXECUTED, NOT JUST READ, AND THESE ARE THE NUMBERS THE TEST SHOULD REPRODUCE.** Copied
literally it imports cleanly, `_RULED_DISPOSITIONS == LATCH_DISPOSITIONS`, the five sets are pairwise
disjoint, and the full `11 x 2 = 22`-cell product resolves as: **`pending_r` 11, `decision_r` 5,
`unattributable_r` 3, `away_r` 1, `attested_away_r` 1 — 21 coherent cells — plus exactly ONE raising cell,
`(pending_live, True)`.** An unruled disposition RAISES under BOTH terminality values. Stating the cell
counts rather than only the property means an implementation that quietly drops the membership guard, or
mis-populates `DECISION_DISPOSITIONS`, produces a DIFFERENT histogram and fails visibly instead of passing a
property test that no longer means what it says.

**`decision_r` KEEPS ITS EVIDENCE-KIND SUB-COUNTS (R23 MAJOR, resolved by §A.0's own text).** `decision_r`
sums three DIFFERENT kinds of evidence — directly logged decisions (`accepted`, `declined`), self-attestation
(`attested_acted_manually`, `attested_chose_not_to_act`), and a telemetry-INFERRED lapse
(`discipline_lapse`) — and §A.0 forbids merging categories that differ in evidence kind. §A.0 also states the
remedy exactly: *if they must be summed for a reader, the sum is reported as its own explicitly-named figure
rather than by erasing the distinction upstream.* The distinction IS preserved upstream (three distinct
dispositions), so the fix is at the REPORT: `ExecutionParityReport` carries
`decision_r_logged` / `decision_r_attested` / `decision_r_inferred` alongside the `decision_r` total, and the
CLI prints the three. **The bucket partition is unchanged** — this adds reporting, not a sixth bucket.

**The sub-counts are REFINEMENTS OF TERMINAL `decision_r`, computed AFTER bucketing (R24 MAJOR).** Each
observation is bucketed first via `r_bucket_for(disposition, is_terminal=...)`; **only rows whose bucket is
`decision_r` may enter a sub-count**. Counting by disposition NAME instead would let a LIVE `accepted` into
`decision_r_logged` while its R correctly sat in `pending_r` — so the sub-counts would stop summing to the
total, and the tempting "fix" is to make `decision_r` wrong too. A test with a non-terminal
accepted / declined / attested fixture asserts all three sub-counts are UNCHANGED.

**WHICH BUCKETS ARE SCORED, and it is not all of them.** `classifiable_fires` (the denominator of BOTH away
rates, §F.2) is `decision_r + away_r + attested_away_r` — the TERMINAL, classifiable observations.
`pending_r` and `unattributable_r` are REPORTED with their own counts and enter no denominator. The
`attested_away_r` bucket is in the denominator but **NOT in the discipline signal**: it is a non-judgment
non-action, honoured as attested (§A.1.6 ruling 2).

`ExecutionParityReport` carries **every bucket in `R_BUCKETS`** (§F.3 defines it; the report builds its
fields BY ITERATING that frozenset rather than by listing them, so a sixth bucket cannot be added to the
resolver and silently omitted from the report) — plus each excluded disposition's own count so the REASON is never lost
inside a total. FTRE's +1.22R lands in `unattributable_r` on today's substrate, per RD's ruling. The report also carries
the per-field delta totals and the **agreement rate**, whose numerator and denominator are both explicit:

**THE REPORT'S TIME AXIS IS `recorded_ts`, NOT `action_session_date` (Codex R9 MAJOR 2).** The row carries
both, and the plan never said which one bounds the monthly read — so an implementation filtering on
`action_session_date` would put a validity answer given in August about a July render into JULY, and would
drop a post-month-end CORRECTION out of the current read entirely. Both are silent misbucketings of a
measurement RD reads once a month. So:

- `list_intents_since(conn, *, since_ts)` filters on **`recorded_ts`**, and the CLI cutoff is `recorded_ts`.
- Ordering is **`(recorded_ts, intent_id)`** so same-second writes are deterministic.
- **`action_session_date` is PROVENANCE AND DISPLAY ONLY** — it answers "which session's mandate was this
  about", never "which month does this row belong to". A test asserts a validity row whose
  `action_session_date` is in month N-1 but whose `recorded_ts` is in month N appears in month N's report and
  NOT in month N-1's.
- **Timezone:** `recorded_ts` is server LOCAL wall clock, `datetime.now().isoformat(timespec="seconds")` —
  the same frame 21-A's beacon stamps `first_viewed_ts` / `last_viewed_ts` in. The CLI's `--since` is parsed
  in that same frame and the report PRINTS it, so the two can never be compared across frames silently.

```
agreement_numerator   = place intents with a KNOWN actual side, OrderDelta.any_difference is False,
                        AND execution_outcome == 'accepted_by_broker'
agreement_denominator = place intents with a KNOWN actual side AND execution_outcome == 'accepted_by_broker'
reported alongside, NEVER folded in:
    validity_unknown       -- place intents whose execution_outcome is 'unknown'
    validity_failed        -- 'rejected_by_broker' or 'not_submitted'
    actual_side_unknown    -- no observed/attested actual params yet
```

**A place intent that the broker rejected is a FINDING, not an agreement and not a disagreement** — the
framework and the operator may have agreed perfectly on an order the market would not accept, which is
precisely the FTRE class stage 2's `preview_order` exists to kill. Reporting it in its own count is what makes
that visible; folding it into either the numerator or the denominator would hide it. In V1 `validity_unknown`
will dominate (validity is only ever attested — §M.5), and the report says so on the same line rather than in
a footnote, so a small agreement denominator can never be mistaken for a strong result.

---

## G. Web (B7's four hazards)

### G.1 Hazard (a) — double-click / refresh -> a per-latch IDEMPOTENCY KEY, not a disabled button

The key is **content-derived**, not a render-time nonce, so a REFRESH followed by an identical resubmit also
collapses (a nonce would not):

```python
def _digest(*parts: str) -> str:
    """LENGTH-PREFIXED, never delimiter-joined (Codex R12 MAJOR 2).

    A single-character '|' join is ambiguous the moment a component can CONTAIN
    that character -- and one of them is `decline_reason`, free operator text.
    Two different decisions could then produce the same pre-hash string and
    collapse onto one ledger row, or replay the wrong one. Length-prefixing
    makes the encoding injective, so distinct inputs cannot share a digest.
    """
    h = hashlib.sha256()
    for part in parts:
        raw = part.encode("utf-8")
        h.update(str(len(raw)).encode("ascii"))
        h.update(b":")
        h.update(raw)
    return h.hexdigest()

idempotency_key = _digest(
    "v1", str(candidate_id), session_component, surface, intent_kind,
    anchor_digest, actual_digest)
```

**THE SESSION COMPONENT IS KIND-SCOPED, AND IT IS NOT ALWAYS `action_session_date` (Codex R25 MAJOR).**
Since a `validity` row's `action_session_date` is SERVER-COPIED from its parent (§C.2), using it here would
force a parent-row DB READ *before* the step-4 replay `SELECT` — breaking this section's load-bearing
property that **every key input is a function of the submitted payload alone**, which is exactly what lets
step 3 precede step 4. So:

```python
session_component = (
    action_session_date                          # place / decline / cancel / attest:
                                                 #   the VALIDATED anchor, which IS the
                                                 #   value that will be stored
    if intent_kind != "validity"
    else f"parent:{validated_place_intent_id}")  # validity: the parent link, which is
                                                 #   IN the payload and pins the mandate
                                                 #   session uniquely and immutably
```

**No discriminating power is lost on the validity branch, and that has to be checked rather than assumed:**
two answers about DIFFERENT parents differ via `validated_place_intent_id` (here AND in `actual_digest`); two
DIFFERENT answers about the SAME parent differ via `validity_outcome` (in `actual_digest`); two IDENTICAL
answers about the same parent are the replay this key exists to collapse. And because
`latch_order_intents` is append-only, `validated_place_intent_id -> action_session_date` is an immutable
function — so the parent link is a strictly BETTER stand-in for the mandate session than the anchor, which
moves every day. A test asserts a validity answer re-submitted the NEXT SESSION (same parent, same answer,
newer anchor) produces the SAME key and replays as `200` with the same `intent_id` — an implementation using
the current anchor writes a SECOND row and FAILS.

`anchor_digest` and `actual_digest` are built with the SAME `_digest` helper over their own component lists,
so the property holds all the way down. A test plants a `decline_reason` containing `|`, `:` and a digit run
and asserts two distinct decisions produce distinct keys.

**`anchor_digest` IS KIND-SCOPED TOO, FOR THE SAME REASON `session_component` IS (Codex R26 MAJOR).**
Scoping only the session component was half a fix: `anchor_digest` still covered `view_session_date` *exactly
as submitted*, so a next-session re-render changed the digest and therefore the key — and this section's own
newly-added replay claim (and its test) would have failed against the plan as written. The two components
have to move together.

- **`place` / `decline` — UNCHANGED.** `anchor_digest` is the canonical (sorted-key, fixed-format)
  serialisation of **EVERY hidden field the form emitted** — `view_session_date`, `candidate_id`, all five
  `framework_*` fields and **EVERY `derivation_*` column the table declares** — discovered from the schema,
  never from a list or a count here (a count is what let three of them go un-anchored) — **exactly as
  SUBMITTED**. It is NOT the session
  anchor alone (Codex R5 MAJOR 3): if the key covered only the session and the operator's answer, a tampered
  or stale form carrying a DIFFERENT framework order but the same session and answer would hit the replay
  `SELECT` at step 4 and return `200` **without ever reaching the step-5 comparison** — a laundering path
  straight through the hazard-(b) defence. That threat is real precisely BECAUSE these kinds submit a
  framework anchor.
- **`validity` / `cancel` / `attest` — `anchor_digest` is the digest of `candidate_id` ALONE.** These kinds
  submit NO framework block at all (§C.2 makes one unwritable on them), so there is no framework anchor to
  launder and nothing for the R5 defence to protect; what remains in the old definition is exactly the
  render-time session, which is what breaks replay. Excluding it costs nothing: a `validity` row is already
  pinned by `validated_place_intent_id` + `validity_outcome` + `broker_snapshot_digest` (all in
  `actual_digest`), and `cancel`/`attest` are pinned by `session_component` (their anchor) plus their own
  answer fields. **`view_session_date` remains fully load-bearing as a VALIDATION on every kind** — the
  four-tier ladder still runs at step 5 — it simply stops being KEY material where it cannot discriminate.
  This is the same distinction the section already draws for `broker_snapshot_ts`: a gate is not a key input.
`surface` is in the key because the table makes it a first-class NOT NULL column and this arc exists partly to
keep 21-F's surface architecture open (Codex R10 MAJOR 3): without it, an identical decision taken from a
second surface would collapse onto the first row and the ledger would lose which surface actually wrote the
intent — the same defect §C.1 fixes on the telemetry side.
**`actual_digest` DIGESTS THE NORMALISED SUBMITTED PAYLOAD.** `normalise_submitted(payload)` runs FIRST —
`canonical_duration(raw_duration)` (§D.4) plus display-rounding on every numeric field — because two
semantically identical answers (`GTC` vs `GOOD_TILL_CANCEL`) must not produce different keys while persisting
the same canonical value; that would write a duplicate ledger row on a plain reload. Normalisation is a PURE
function of the payload and touches no server state, so the "nothing in the key depends on the re-derivation"
property below holds exactly.

**`actual_digest` covers EVERY operator-submitted SEMANTIC field for the kind** — the normalised `actual_*`
params, `decline_reason`, `attested_disposition`, `validity_outcome`, `actual_broker_order_id`,
`validated_place_intent_id`, and `broker_snapshot_digest`. The answer fields are named explicitly because
omitting them lets two DIFFERENT answers for the same parent and snapshot (`rejected_by_broker` vs
`not_submitted`) collide, so step 4 would replay the first as a `200` and the second answer would be silently
lost. Pairwise tests differ only by `validity_outcome`, and only by `attested_disposition`, and assert
distinct keys.

It deliberately does **NOT** cover `broker_snapshot_ts`: that is render-time data changing on every reload, so
keying on it would give a plain refresh a new key and duplicate the row — falsifying this section's own
collapse-on-refresh property for the one form that most needs it. The timestamp still drives the staleness
GATE (a validation, not a key input) and is still persisted in `validity_detail`.

**TWO DISTINCT COUNTERS, NAMED APART.** **`attributable_order_count`** (21-A's frozen-price `_match_latch`)
drives the prompt branch and the multiplicity gate; **`exact_framework_match_count`** drives the agreement
wording. Reusing 21-A's single `matched_order_count` for both gives an implementer two incompatible meanings
and routes FTRE's real `LIMIT 18.89 / 10 sh` down the ABSENCE path instead of the divergence path. Both
counters are persisted in the snapshot envelope and both are asserted in Task 7, and a grep pin (Task 10)
asserts the bare name `matched_order_count` appears NOWHERE in 21-B's own code or tests (21-A's field keeps
its name on `LatchOrderJoin`; every 21-B consumer must name which question it is asking).

`broker_snapshot_digest` is derived instead from the broker-book STATE the fragment showed — `resolution.kind`,
`attributable_order_count`, `exact_framework_match_count`, `indeterminate`, **and a canonical digest of EVERY resting BUY order visible on this
ticker** (order id, type, duration, stop, limit, quantity, status, all at display precision), sorted by order
id — via the same `_digest` helper. **The per-order tail is load-bearing, not decoration (Codex R17 MAJOR):**
with only the counts and the matched id, an EMPTY book and a book containing one NON-matching FTRE order hash
identically whenever `attributable_order_count == 0` — and the non-matching order is precisely the actual side the
parity ledger needs. The digest would then fail "changes when it MUST" on the arc's own geometry. With the
tail it is identical across reloads that show the same book and different the moment the book actually moves —
exactly the equivalence relation an idempotency key wants. `broker_snapshot_ts` still travels in the payload,
still drives the §F.3 staleness gate (a VALIDATION, not a key input), and is still persisted into
`validity_detail` for audit. Every digest input is a function of the SUBMITTED PAYLOAD ALONE (normalised, but
never enriched from server state) — **nothing in the key depends on the re-derivation**, which is what makes
the handler ordering below possible.

**The discriminating test (Task 7):** POST, then re-POST with ONE hidden field mutated. The key must CHANGE,
so step 4 misses, step 5 runs, and the response is `409` — not a `200` replay. An implementation whose key
omits the framework snapshot returns `200` and FAILS.

**THE EXACT HANDLER ORDER (Codex R1 MAJOR 1 — the plan's first draft was neither replay-safe nor race-safe):**

```
1. parse the form                          -> 400 on an unparseable body
2. SHAPE-validate every field              -> 400 naming the offending field
   (types, ranges, enum membership, the intent_kind conditional requirements)
3. NORMALISE the submitted payload, then derive idempotency_key from it
4. SELECT ... WHERE idempotency_key = ?    -> FOUND: REPLAY. 200 + the same
                                              fragment + the same intent_id.
                                              *** RETURN HERE. NEITHER the anchor
                                              staleness check NOR the broker-
                                              snapshot freshness check is run. ***
5. FIRST-WRITE VALIDATION ONLY:
   (a) anchor staleness (the four-tier ladder)     -> 409
   (b) broker-snapshot freshness, for a `validity` -> 409
   (c) re-derive AS OF the submitted anchor + compare -> 409 on any field mismatch
6. INSERT ... ON CONFLICT(idempotency_key) DO NOTHING
7. SELECT by idempotency_key and return THAT row   -> covers the lost race
```

Three properties this ordering buys, each with its own test:

- **A replay is never `409`'d — and that covers the BROKER SNAPSHOT as well as the session anchor (R22
  MAJOR).** Step 4 returns before step 5, so a retry of an ALREADY-RECORDED intent succeeds even after the
  world has moved. Recording the intent is the terminal state; once it exists, neither a stale anchor nor a
  snapshot older than `LATCH_BROKER_SNAPSHOT_MAX_AGE_SECONDS` is relevant to it. The freshness gates exist to
  stop a stale view producing a NEW row, not to punish a resubmit of a row already written. A test replays a
  `validity` submission whose snapshot is older than the bound and asserts `200` + the same `intent_id`, not
  `409`.
- **The concurrent race cannot 500.** Two requests can both miss step 4; `ON CONFLICT DO NOTHING` + the
  re-SELECT at step 7 means the loser returns the winner's row rather than surfacing an `IntegrityError`.
  (`ON CONFLICT DO NOTHING` is an INSERT-time no-op, NOT `INSERT OR REPLACE` — no DELETE, no new PK, no
  cascade. The append-only property holds.)
- **The SELECT-first idempotency gotcha is now HONORED, not inverted.** The first draft derived the key after
  a re-derivation and had to argue the gotcha away; this ordering satisfies it literally — the terminal-state
  SELECT precedes the expensive/fragile validation. That the gotcha's shape reasserted itself here is the
  reason to follow it rather than reason around it.

Two further notes:
- **V1 semantic, stated as a limitation:** two genuinely separate identical decisions in ONE session collapse
  to one row. The ledger records DECISIONS, not clicks. Banked as V2 if RD ever wants click-level fidelity.
- **NEVER `INSERT OR REPLACE`** (the DELETE+INSERT / new-PK / cascade gotcha). The table is append-only.

### G.2 Hazard (b) — GET/POST staleness -> a HIDDEN ANCHOR, validated, never silently recomputed

The form emits the framework computation as hidden inputs: `view_session_date`, `candidate_id`,
`framework_order_type`, `framework_duration`, `framework_stop_price`, `framework_limit_price`,
`framework_quantity`, plus **EVERY `derivation_*` column the table declares** — enumerated from the schema,
not from a hand-kept list, so a column added to the DDL cannot be silently left out of the anchor (Codex R27
MAJOR: three were). A test asserts the set of emitted `derivation_*` hidden inputs EQUALS the set of
`derivation_*` columns on `latch_order_intents`. At POST:

1. **The session anchor gets the SAME four-tier ladder the 21-A beacon already ships**
   (`swing/web/routes/latches.py:_parse_beacon_anchor` / `_classify_anchor`): unparseable -> `400` naming the
   field; future -> `400`; non-NYSE-session -> `400`; more than one session stale -> `409` + a LOUD fragment
   telling him to reload. The four-tier shape and its rejection prose are REUSED, not re-invented.
2. **RE-DERIVE AS OF THAT ANCHOR** — `build_latch_derivation(conn, cfg, horizon_session_override=anchor)` —
   and recompute the prepared order for `candidate_id`. This is the 21-A beacon's exact pattern.
3. **COMPARE, field by field, at display precision. ANY difference -> `409` + a fragment that NAMES the
   changed fields and their old/new values, and the intent is NOT recorded.** The handler never substitutes
   the fresh computation for the anchored one. The gotcha is explicit: *validate the POST against that exact
   anchor's row; don't recompute "latest" at POST time.* Re-deriving to VALIDATE is not substituting.
3b. **STEPS 2-3 ARE THE DECISION KINDS' VALIDATION ONLY.** Re-deriving a prepared order and comparing it
   field by field is meaningful for `place` and `decline`, which submit one. `validity`, `cancel` and
   `attest` submit NO framework block (§C.2 makes one unwritable on them), so there is nothing to compare and
   the handler MUST NOT invent a comparison — it would 409 every attestation the moment the underlying
   derivation moved, which for an aged prompt is always. Their first-write validation is: the four-tier
   anchor ladder (step 1, unchanged), plus — for `validity` only — the broker-snapshot freshness gate (§E).
   A test asserts an `attest` submitted a week after the latch went terminal is ACCEPTED, and that a
   `validity` answer about a month-old `place` intent is ACCEPTED so long as its broker snapshot is current.
4. `recorded_ts` is SERVER-STAMPED wall clock. **`action_session_date` is NOT uniformly the anchor** — it is
   the MANDATE's session per §C.2's per-kind table: the validated anchor for `place`/`decline`/`cancel`/
   `attest`, and SERVER-COPIED from the parent `place` row for `validity`. The handler reads the parent row
   for that value; it never takes it from the payload on any kind. A test asserts a `validity` row answering
   a `place` intent from session N-20 stores `action_session_date` = N-20 while `recorded_ts` is today —
   which is also what makes §F.3's "month N report, month N-1 mandate" case true rather than merely asserted.
   No timestamp is
   ever read from the payload (the V1 server-stamp gotcha).
5. **Why this is strict and stays strict:** the sizing equity moves when an exit or a cash movement lands, so
   an equity change between render and click WILL force a reload. That is the correct direction. The ledger's
   entire value is that the recorded framework order is byte-identically what the operator was looking at; a
   handler that quietly re-sized would record an order he never saw.

The form is a real `<form>` inside an HTMX-rendered page, so it carries `hx-headers='{"HX-Request": "true"}'`
(OriginGuard `strict=True` is hardcoded at `swing/web/app.py:656` and 403s an unsafe method without it).

### G.3 Hazard (c) — CANCEL targets a specific broker order id, never a ticker

The Cancel control renders **only** on the order fragment's `ORDER_RESTING_LATCH_CLEARED` alarm rows and on a
matched order line, and it carries that order's `order_id` as a hidden input. `intent_kind='cancel'` with a
blank/absent `actual_broker_order_id` is rejected at THREE layers: the form does not emit one, the handler
`400`s, and the schema `CHECK` makes the row unwritable (§C.2). A grep test asserts no cancel path anywhere
takes a ticker as its target. **The button LOGS the intent; no Schwab call is made** (the global constraint's
grep pin covers this).

### G.4 Hazard (d) — framework-vs-operator distinguishability in the recon path

`latch_order_intents` is the register — but **EXACT linkage comes from a `validity` or `cancel` row, NEVER
from a `place` row** (Codex R20 MAJOR). The draft said "a `place` intent with `actual_broker_order_id` set",
which §C.2 now makes UNWRITABLE (a decision row has observed nothing, R19 MAJOR): an implementer following it
would either write code the schema rejects or build report logic around a column state that can never exist.
A `validity` row carries the observed `actual_broker_order_id` AND `validated_place_intent_id`, so the join
`place -> validity -> broker order id` is exact and travels through the parent link; a `cancel` row carries
the id directly. Because 21-B places nothing, the linkage is established when the operator answers the
validity prompt — and that prompt fires on **LATCH ATTRIBUTION** (`_match_latch`, frozen-price based), NOT on
an exact framework-params match (§E). The distinction is the whole reason FTRE is recordable: its actual
`LIMIT 18.89 / 10 sh` does NOT match the framework `9 sh`, so an exact-match linkage rule would make the arc's
central divergence unlinkable and therefore unrecordable. `exact_framework_match_count` is an input to the
AGREEMENT WORDING and the metric — never to linkage. V1 therefore delivers **distinguishability as a QUERY,
not as an order tag** — which is all that is available before 21-C, and it is stated as such:

- `swing latches parity` reports, per resting order at the broker, an **`inferred_origin`** of
  `framework_inferred` (its params match a recorded `place` intent at display precision),
  `operator_inferred` (it matches a latch's frozen prices but no `place` intent), or `unattributed`
  (neither). **The field is named `inferred_origin` and never `origin`, and the report prints the inference
  basis next to it** (Codex R4 MAJOR 1 — the first draft said the question was "answerable for every
  historical row from the ledger alone", which is an overclaim: a params match is a heuristic, and two
  identical orders are indistinguishable by params).
- **The one place V1 IS exact:** where a broker order id was captured on a `cancel` or `validity` row
  (§C.2 — both carry `actual_broker_order_id`), THAT order's association with a ledger row is exact rather
  than inferred. The report distinguishes the two cases rather than averaging them.
- **The V2/21-C dependency is named:** a real broker-side tag (a client order id echoed by Schwab) is the only
  thing that makes this exact IN GENERAL, and it cannot exist until something places an order. Until then the
  report may not present inference as identity.

### G.5 The endpoint

`POST /latches/intent` returns an HTML fragment (`200`) on success. `GET` on that path must be **405**, pinned
by a test.

**THIS DELIBERATELY DEPARTS FROM THE PROJECT'S HTMX FORM CONTRACT, and the departure is argued rather than
assumed (Codex R2 MAJOR 1).** The gotcha reads: *"success path must be `204` + `HX-Redirect: <url>`, NOT
`303` -> swap-target (htmx.js swallows 303)."* Its subject is **navigation**: a `303` is swallowed, so a form
that must send the operator somewhere else has to use `HX-Redirect`. `POST /trades/entry` is that shape — it
navigates to the dashboard.

**This endpoint must NOT navigate.** The operator's task is per-latch and there is usually more than one latch
on the page; bouncing him to a fresh page after each decision would force a re-render, re-fire the beacon and
the broker fragment, and lose his place. So the success response swaps the card's own block in place. That is
the `POST /latches/orders` + `POST /prices/refresh` shape (a POST returning markup), both shipped and both
browser-verified. Consequences that MUST be honored or this becomes the very bug the gotcha describes:

- The form carries **explicit `hx-target` and `hx-swap`** — `hx-target="this"` on the form's own wrapper (the
  ancestor-inheritance gotcha: the card sits inside `.latch-cards` and a future ancestor `hx-target` must not
  capture it) — so the 200 fragment lands in the card, not somewhere unrelated.
- `base.html.j2`'s `htmx.config.responseHandling` 4xx-swap override is what makes the `400` / `409` fragments
  visible at all. **It must be preserved**, and a test asserts it is still present in the rendered base.
- The fragment root is a `<section>`, never a `<tr>` (the `makeFragment` synthetic-table-wrap gotcha).
- `hx-headers='{"HX-Request": "true"}'` on the form (OriginGuard strict-mode 403s an unsafe method without it).
- **This is browser-only territory** — TestClient asserts bodies, not DOM — so the §L GUI witness explicitly
  covers: the 200 fragment swaps into the right card; the 409 stale notice RENDERS; a 400 renders its named
  field. That is why the witness is binding rather than confirmatory.

---

## H. B6 — the separated-claims construction

`LatchOrdersFragmentVM.all_clear_note` currently emits one SCOPED sentence:
`"No alarms among the {N} {latch|latches} form-checked. {M} not form-checked - see the labels below."`

**Why it is wrong** (RD, 2026-07-28): it rests on a misunderstanding. Only the two-form SELECTION is skipped —
alarms, the cap leg, GTC duration and the stray-order sweep all RUN on every latch. So the alarm all-clear is
**not scoped at all; it is COMPLETE**. And the scoped form produces a **vacuous zero-case** in the ~7-hour
window when `form_check_ran_count == 0`: "No alarms among the 0 latches form-checked."

**The premise was re-verified on disk before adopting it:** on the no-findings branch (the only branch that
reaches `all_clear_note`, `partials/latch_orders.html.j2:22-32`) there are no alarms, no disagreements, no
indeterminate tickers and no multiplicity notes; `join_orders_to_latches` ran over `derivation.latches`
unconditionally. Every latch WAS alarm-checked. The claim holds.

**The replacement — separate claims, each independently true, none vacuous:**

```
"No alarms."                                                  # always, on this branch
"Mandate-form check pending for P latches."                   # iff P > 0
"Mandate-form check inert for Q latches - see the labels below."   # iff Q > 0
"Mandate-form check status unknown for U latches."            # iff U > 0
```

`P` / `Q` / `U` are the counts of `mandate_form_check_skipped` notes with severity `pending` / `permanent` /
`unknown`. **The pending-vs-permanent distinction is carried into the page-level line**, which is the B6
refinement: today it is visible only in the per-latch labels, so the page-level sentence lumps a
self-resolving wait together with a permanently-inert latch. `form_check_ran_count` stays on the VM (the CLI
report and the tests read it) but no longer appears in the prose — the operator does not need a denominator
for a claim that is not scoped.

Tests: the zero-case (`P>0, ran=0`) renders `"No alarms."` and never the substring `"among the 0"`; the
all-checked case renders `"No alarms."` and nothing else; a mixed pending+permanent case renders three
sentences with the right counts; `all_clear_note` is still unreachable from every findings branch.

---

## I. File structure

**Create**

| path | responsibility |
|---|---|
| `swing/data/migrations/0033_latch_order_intents.sql` | the `latch_view_events` rebuild (+`surface`) + `latch_order_intents` + `schema_version` 32->33 |
| `swing/data/repos/latch_order_intents.py` | `record_intent` — the IDEMPOTENT WRITE ONLY (§G.1 steps 4, 6, 7: SELECT-by-key, `INSERT ... ON CONFLICT DO NOTHING`, re-SELECT), under the caller's transaction, with NO HTTP parsing, NO re-derivation and NO fragment rendering. **The ROUTE owns steps 1-3 and 5 and all responses** (R22 MAJOR — the first draft assigned "the seven-step order" to the repo, which pushes web and derivation concerns into the data layer). `list_intents_for_latch`, `list_intents_since(*, since_ts)` — filtering and ordering on `recorded_ts` (§F.3) |
| `swing/latches/order_intent.py` | `PreparedOrder`, `OrderDerivation`, `PreparedOrderResult`, `compute_prepared_order`, `OrderDelta`, `compute_order_delta` — PURE |
| `swing/latches/classification.py` | `LatchDisposition`, `classify_latch`, `TelemetryHealth`, `assess_telemetry_health`, `AwayRateResult`, `ExecutionParityReport`, `compute_execution_parity` — PURE |
| `swing/cli_latches.py` | `swing latches parity` — read-only report; ASCII only |
| `swing/web/templates/partials/latch_prepared_order.html.j2` | the form block (offered + withheld branches) |
| `swing/web/templates/partials/latch_intent_result.html.j2` | the POST success / replay / 409 fragment |
| `tests/latches/test_order_intent.py`, `test_classification.py`, `test_telemetry_health.py`, `test_execution_parity.py` | derivation + classification tests |
| `tests/data/test_migration_0033.py`, `tests/data/test_latch_order_intents_repo.py` | schema + repo tests |
| `tests/web/test_routes/test_latches_intent_route.py`, `tests/web/test_view_models/test_latch_prepared_order_vm.py` | web tests |
| `tests/cli/test_cli_latches_parity.py` | CLI report tests (incl. a PowerShell stdout-encoding subprocess test) |
| `tests/latches/test_no_schwab_write_endpoints.py` | the L2-style grep pin |

**Modify**

| path | change |
|---|---|
| `swing/data/db.py` | `EXPECTED_SCHEMA_VERSION` 32->33; `PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES`; `_create_pre_phase21_arc_b_migration_backup`; `_phase21_arc_b_backup_gate`; wire into `run_migrations` |
| `swing/data/models.py` | `LatchOrderIntent` dataclass + `__post_init__`; **`LatchViewEvent` gains `surface` and ALL THREE of `actionable_at_first_view` / `actionable_at_last_view` / `actionable_ever_viewed`** with `{0,1}` validation on each plus the two `ever >= first` / `ever >= last` monotonicity checks (and NO first-vs-last constraint — §C.1); the new enums IMPORTED from `swing/latches/constants.py`, never re-declared |
| `swing/data/repos/latch_view_events.py` | RE-KEYED on `(candidate_id, view_session_date, surface)` (§C.1) — `get_view` / `record_view` take `candidate_id` + a REQUIRED `surface`; `_COLS` and `_row_to_model` gain `surface` + ALL THREE actionability columns, named exactly — `actionable_at_first_view`, `actionable_at_last_view`, `actionable_ever_viewed` (a test asserts `_COLS` EQUALS the rebuilt table's PRAGMA column list, so an omitted `ever` — the one CLASSIFICATION reads — cannot ship green); `record_view` gains `actionable=`; both list helpers gain an explicit `surfaces=` filter |
| `swing/latches/constants.py` | `LATCH_TELEMETRY_EPOCH_SESSION`, `LATCH_VIEW_SURFACES`, `ACTIONABLE_VIEW_SURFACES`, `LATCH_INTENT_KINDS`, `LATCH_ATTESTED_DISPOSITIONS`, `LATCH_VALIDITY_OUTCOMES`, `LATCH_DISPOSITIONS`, `LATCH_SIZING_BASES`, `LATCH_STOP_LEG_STATES`, `LATCH_ORDER_WITHHELD_REASONS`, `LATCH_TELEMETRY_DARK_SESSIONS_THRESHOLD`, `LATCH_BROKER_SNAPSHOT_MAX_AGE_SECONDS`, `LATCH_BROKER_SNAPSHOT_KEYS` (the SEVEN, §C.2 — imported by the fragment, the handler, the dataclass validator and the drift test, so the emitted set and the required set are ONE object), **`LATCH_BROKER_SNAPSHOT_RENDER_BRANCHES` and `LATCH_BROKER_SNAPSHOT_PERSISTED_BRANCHES`** (the two vocabularies, §C.2 — the JSON-expressed enum is a schema enum and takes the #11 mirror like every other, which it had escaped purely because it is written as a `json_extract` predicate rather than a column CHECK); **and the FIVE bucket sets §F.3 defines** — `AWAY_RATE_COUNTED_DISPOSITIONS` (fixed at `{"away_unseen"}` per §A.1.5), `ATTESTED_AWAY_DISPOSITIONS`, `PENDING_DISPOSITIONS`, `DECISION_DISPOSITIONS` (written out, never derived) and the derived `UNATTRIBUTABLE_DISPOSITIONS`, plus `_RULED_DISPOSITIONS` (their union — what `r_bucket_for` validates against), `R_BUCKETS` (the closed set of values `r_bucket_for` RETURNS — the report, the partition test and the CLI all ITERATE it), and `DERIVATION_NULLABLE_ON_DECISION` (the two derivation columns legitimately NULL on a decision row, §C.2) |
| `swing/web/routes/latches.py` | **(a)** NEW `POST /latches/intent` (the §G.1 seven-step handler). **(b) `POST /latches/view` IS REWRITTEN, not merely passed a new kwarg (Codex R13 MAJOR 3):** `_parse_beacon_anchor` gains `actionable_candidate_ids` + `withheld_candidate_ids` REPLACING the single `candidate_ids` field (same rejection ladder, same 200-id cap applied to the UNION, plus a rejection when an id appears in BOTH lists); the handler intersects EACH list with the anchor-session live set and calls `record_view(..., surface="latch_panel", actionable=<which list it came from>)`. **If this route is left on the old contract every withheld render is still ingested as a plain view and the whole R7 fix never reaches the DB.** **(c)** `POST /latches/orders` gains the validity prompt + the SINGLE `broker_snapshot_json` hidden field carrying every key in `LATCH_BROKER_SNAPSHOT_KEYS` (§C.2's `json_remove` path list is the roster) — NOT separate `broker_snapshot_ts` / `broker_snapshot_branch` inputs, which cannot satisfy the envelope contract |
| `swing/web/view_models/latches.py` | `LatchRowVM` gains the prepared-order + disposition + prompt block; `LatchPanelVM` gains the intent-anchor payload (**and `PANEL_SPECIFIC_FIELDS` grows to match**); `all_clear_note` -> the separated claims |
| `swing/web/templates/latches.html.j2` | include the prepared-order partial per live card; the attestation prompt on terminal cards |
| `swing/web/templates/partials/latch_orders.html.j2` | the separated-claims render; the per-order Cancel control on stale-order rows |
| `swing/web/static/app.css` | `var()`-only tokens for the form / prompt / disposition badges (no raw hex — the theme-token contract test) |
| `swing/cli.py` | `main.add_command(latches_group)` |

---

## J. Tasks

### Task 1: Schema + models + constants + repo (the #11 one-commit multi-mirror task)

**Files:** create `0033_latch_order_intents.sql`, `swing/data/repos/latch_order_intents.py`; modify
`swing/data/db.py`, `swing/data/models.py`, `swing/data/repos/latch_view_events.py`,
`swing/latches/constants.py`. Tests: `tests/data/test_migration_0033.py`,
`tests/data/test_latch_order_intents_repo.py`, plus the 0032-preservation suite (below).

- [ ] **Step 1: failing tests.** Must include, at minimum:
  - `EXPECTED_SCHEMA_VERSION == 33`.
  - The identity block is columns 2-6 and EQUALS `LATCH_IDENTITY_COLUMNS` (the 21-A contract, mechanically
    pinned on the NEW table too).
  - `candidate_id` NOT NULL; deleting the referenced `candidates` row raises `IntegrityError` (RESTRICT).
  - Every CHECK: each `intent_kind`, a `decline` with a blank reason, an `attest` with no disposition, a
    **`cancel` with no `actual_broker_order_id`**, a `place` missing any framework field, a bad
    `framework_order_type`, a bad `validity_outcome`.
  - **THE DATE/TIME GUARD, BOTH HALVES, PINNED INDEPENDENTLY (§C.1.1, RD's condition 2).** For EVERY date and
    timestamp column carrying a `CHECK` in `0033` — `latch_order_intents.detection_date`,
    `.action_session_date`, `.recorded_ts`, `.derivation_regime_close_session`, the
    `validity_detail` JSON `broker_snapshot_ts` / `broker_snapshot_session`, and the rebuilt
    `latch_view_events.detection_date` / `.view_session_date` — **TWO separate tests, never one combined**:
    - the **NORMALISING** case (`'2026-02-30'`, and `'2026-07-28T24:00:00'` for the timestamps) is REJECTED —
      this one FAILS against an `IS NOT NULL`-only guard;
    - the **INVALID** case (`'2026-99-99'`, and `'2026-07-28T99:99:99'` for the timestamps) is REJECTED —
      this one FAILS against the round-trip-equality-only guard `0032` shipped.
    - the **YEAR-ZERO** case (`'0000-01-01'`, and `'0000-01-01T00:00:00'`) is REJECTED — this one FAILS
      against BOTH of the above, because SQLite round-trips year zero happily while
      `date.fromisoformat` raises on it (Codex R26 MAJOR: the DB would hold a row the read path cannot
      hydrate). Paired with an ACCEPT of `'0001-01-01'` and `'9999-12-31'`, so the fix cannot be "reject
      anything that looks unusual".
    A single "a malformed date is rejected" test passes with HALF the guard missing, whichever half was
    dropped, so it must not be written that way. **An earlier revision of this very bullet instructed the
    round-trip form and explicitly rejected `IS NOT NULL` as "weaker" — following it would have reproduced the
    shipped defect in the new table.**
  - `UNIQUE(idempotency_key)` blocks a second row.
  - The IMMUTABILITY BARRIER: `UPDATE` and `DELETE` on `latch_order_intents` both ABORT, and the message names
    the append-only rule.
  - **`recorded_ts`, EVERY REJECTION CELL SEPARATELY (R19 MAJOR + Codex R25 MAJOR — this column drives the
    monthly report's cutoff and ordering).** ACCEPT `'2026-07-28T12:00:00'` and `'2026-07-28T23:59:59'`.
    REJECT, each as its own case: wrong length; **`'2026-07-28 12:00:00'` (a SPACE separator)**;
    **`'2026-07-28T24:00:00'` (hour 24)**; `'2026-07-28T12:60:00'`; `'2026-99-99T12:00:00'`;
    `'2026-02-30T12:00:00'`; `'2026-07-28TAB:00:00'` (non-digits in the time). **The space and hour-24 cells
    are the discriminators** — the pre-R25 CHECK `datetime(x) = replace(x,'T',' ')` ACCEPTS both, verified
    empirically, so a test omitting them passes against the defective guard. Mirrored in
    `LatchOrderIntent.__post_init__`.
  - `actual_broker_order_id` blank-when-present is REJECTED on every kind, and a `place` or `decline` row
    carrying one at all is REJECTED (R19 MAJOR — a decision row has observed nothing).
  - **THE `validity_detail` ENVELOPE — ONE REJECTION TEST PER MISSING KEY, PLUS THE DEGENERATE SHAPES (Codex
    R25 CRITICAL).** A `validity` row is REJECTED when `validity_detail` is NULL, is not `json_valid`, is a
    JSON ARRAY, is a JSON SCALAR, is the EMPTY OBJECT `{}`, **or is missing ANY ONE roster key** —
    the cases are GENERATED by iterating `LATCH_BROKER_SNAPSHOT_KEYS` and dropping each in turn, so a key
    added to the roster gains its own case automatically instead of needing this bullet edited. **The empty-object
    and missing-key cases are the discriminators and they are not theoretical:** verified empirically, the
    bare presence-and-shape CHECK chain ACCEPTS `{}`, because a missing key makes `json_extract` return NULL
    and a SQLite CHECK PASSES on NULL — the same class as §C.1.1, in JSON syntax. Also REJECT a bad
    `broker_snapshot_branch`, a 63-char or non-hex `broker_snapshot_digest`, a `broker_snapshot_ts` with a
    space separator or hour 24, a `broker_snapshot_session` of `'2026-02-30'` (the NORMALISING case — it
    passes an `IS NOT NULL`-only guard) and of `'2026-99-99'` (the INVALID case), a negative or non-integer
    count, and a string `"true"` for `indeterminate`. **Also REJECT `broker_snapshot_branch='unavailable'`
    on a `validity` row** (Codex R26 MAJOR) — §E renders no prompt against an unknown order book, so an
    append-only row asserting an outcome with an `unavailable` snapshot must be unwritable, not merely
    unreachable; `'presence'` and `'absence'` are ACCEPTED, so the test discriminates a narrowed enum from a
    broken one. **Every rejection must surface as `IntegrityError`, not
    `OperationalError`** — assert the exception TYPE, because a chain that calls `json_extract` outside a
    `CASE WHEN json_valid(...)` gate raises `OperationalError('malformed JSON')` on a non-JSON value, and a
    test catching bare `Exception` would go green against that weaker DDL. The same seven-key contract is
    mirrored in the repo + dataclass validator under #11.
  - A `validity_outcome='accepted_by_broker'` row missing ANY of `actual_order_type` / `actual_duration` /
    `actual_limit_price` / `actual_quantity` is REJECTED (R20 MAJOR).
  - Every PROVENANCE CHECK: a bad `framework_duration`, a bad `derivation_sizing_basis`, a regime close
    WITHOUT its session (and the reverse). **Positivity is specified BY COLUMN NAME in its own bullet
    below — do NOT generalise it to "equity", which would wrongly bound `derivation_real_equity`.**
  - **The FK/immutability coherence test (the R13 CRITICAL, whose assertion the R16 CRITICAL then caught the
    DDL violating):** deleting a referenced `risk_policy` row raises `IntegrityError` (RESTRICT) rather than
    attempting a SET-NULL cascade `trg_loi_no_update` would abort with a confusing message. The test PARSES
    the migration SQL and asserts the substring `SET NULL` appears NOWHERE in the `latch_order_intents`
    statement — a prose rule survived three rounds while the DDL contradicted it, so the assertion has to read
    the DDL, not the intent. It also asserts `pipeline_run_id` carries NO `REFERENCES` clause on this table
    (§C.2: the referent is legitimately pruned and the recorded identity must outlive it).
  - The VALIDITY-PARENT TRIGGER, **all THREE legs** (kind, candidate, session — Codex R25 MAJOR): a
    `validity` row pointing at a `decline` / `cancel` / `validity` row, or at a `place` row on a DIFFERENT
    `candidate_id`, is REJECTED. **The SESSION leg gets its own pair, and the pair is the discriminator:**
    the aged prompt — parent `place` in session N, child written in session N+20 carrying
    `action_session_date` = N (the parent's) and `recorded_ts` in N+20 — is **ACCEPTED**; the SAME child
    carrying `action_session_date` = N+20 (i.e. an implementation that reached for the submitted anchor
    instead of copying the parent) is **REJECTED**. Without the second half the test passes against a trigger
    with no session leg at all.
  - **Its own red test: a `validity` row with `validated_place_intent_id = NULL` is REJECTED** (Codex R16
    MAJOR 3). The parent-link TRIGGER fires only `WHEN NEW.validated_place_intent_id IS NOT NULL`, so it is
    structurally blind to the NULL case; only the CHECK catches it, and without a test aimed at the CHECK an
    orphan validity row goes green and the parent-scoped execution-outcome model silently loses its anchor.
  - A `validity` row requires BOTH `validity_outcome` and `validated_place_intent_id`; a
    `place`/`decline`/`cancel`/`attest` row carrying any of the three validity columns is REJECTED.
  - A `validity` row MAY carry the observed `actual_*` order params (R17 CRITICAL) and MAY NOT carry any
    `framework_*` / `derivation_*` value; a `place` row MUST carry the whole drift-capable derivation block
    (a `place` with NULL `derivation_sizing_equity` is REJECTED — R17 MAJOR), **including
    `derivation_real_equity` and `derivation_equity_floor`** (Codex R27 MAJOR). **The required set is
    asserted AS A SET DIFFERENCE, never as a hand-kept list or a count** —
    `required = {every derivation_* column in PRAGMA table_info} - DERIVATION_NULLABLE_ON_DECISION`. For
    every column in `required`, a `place` row with THAT column NULL is REJECTED; **for every column IN
    `DERIVATION_NULLABLE_ON_DECISION`, a `place` row with it NULL is ACCEPTED** — both loops GENERATED from
    the two sets, so the exemption roster is pinned in BOTH directions, cannot quietly grow, and a new
    derivation column joins `required` without this bullet being edited. A hand-kept
    list is how three of these columns went unanchored in the first place, and an un-pinned exemption list is
    the same failure one size down — Codex R28 MAJOR caught the DDL's required-block CHECK and this very
    bullet disagreeing about `derivation_risk_policy_id`.
  - **THE POSITIVITY BULLET, BY COLUMN NAME (Codex R28 MAJOR).** REJECT non-positive
    `derivation_sizing_equity`, `derivation_equity_floor`, `derivation_zone_cap_pct`,
    `derivation_max_risk_pct`, `derivation_position_pct_cap`, `derivation_nightly_recommendation_shares`,
    `actual_quantity` and `framework_quantity`. **ACCEPT `derivation_real_equity = 0` AND a NEGATIVE
    `derivation_real_equity`** — that is the account, and it is precisely why the floor exists (§C.2). A
    bullet reading "non-positive equity is rejected" without naming the columns invites a CHECK that breaks
    the ruled floor semantics on the one column that must not have one, so the accept-cells are as
    load-bearing as the reject-cells here.
  - **THE ANCHOR/RENDER/STORE CLOSURE IS SPLIT ACROSS THE TASKS THAT OWN EACH SURFACE (§A.4; Codex R27 MAJOR
    raised the invariant, Codex R29 MAJOR corrected its PLACEMENT).** It was written entirely into Task 1,
    whose file scope is schema / models / repos / constants — so it demanded that "the form emits" and "the
    card renders", which live in `swing/latches/order_intent.py` (Task 2) and the VM + templates (Tasks 6
    and 7). Followed literally it would either drag the web layer into the #11 schema commit or leave red
    tests that cannot go green in this task's own files. The invariant is unchanged; only its home moves:
    - **Task 1 (HERE) — the SCHEMA half:** discover the `derivation_*` column set FROM THE DDL; every one
      except the two named exemptions is NOT NULL on `place`/`decline`; both exemptions are NULLABLE;
      `LatchOrderIntent` round-trips all of them through the repo.
    - **Task 2 — the RECOMPUTE half:** `risk_per_share`, `max_risk_dollars`, `shares_by_risk`,
      `shares_by_position_cap` and `binding_constraint` are each reproduced EXACTLY from a stored row plus
      the `candidate_id`-pinned prices — the test that proves they are legitimately DERIVED rather than
      merely omitted from storage.
    - **Tasks 6/7 — the CLOSURE itself:** the set of derivation values the card renders as audited EQUALS
      the set of `derivation_*` hidden inputs the form emits EQUALS the set of `derivation_*` columns on
      `latch_order_intents`. Three sets, asserted equal at the only layer that can see all three, so a value
      cannot be shown without being anchored, or anchored without being stored.
  - **The two raw-append hardening cells added at R29:** a `validity` row whose outcome is NOT
    `accepted_by_broker` carrying ANY `actual_*` value or an `actual_broker_order_id` is REJECTED (and the
    same row with all of them NULL is ACCEPTED); and a malformed `first_viewed_ts` / `last_viewed_ts` on the
    rebuilt `latch_view_events` is REJECTED under the same cells as `recorded_ts` (space separator, hour 24,
    year zero, non-digits), with `last_viewed_ts >= first_viewed_ts` still independently enforced.
  - **Deleting a parent `place` row aborts with the APPEND-ONLY message, not the FK's** (Codex R17 MINOR):
    `trg_loi_no_delete` fires first for any delete here, so a test asserting "self-referencing RESTRICT" would
    prove the wrong thing. Assert the append-only abort text; prove parent-link integrity through INVALID
    INSERTS instead.
  - The shape exclusion: ANY NON-ORDER row (`cancel` / `attest` / `validity`) carrying a `framework_*` or
    `derivation_*` value is REJECTED. **`decline` is an ORDER-BEARING kind and MUST carry the complete
    framework + derivation block** (R18 MAJOR 7) — the pre-R18 wording survived here and directly contradicted
    it, which is a mutually-impossible pair of tests (R19 MAJOR).
  - The REVERSE null checks: a non-`decline` row carrying a `decline_reason`, or a non-`attest` row carrying
    an `attested_disposition`, is REJECTED.
  - The stop-leg conditional: a `STOP_LIMIT` row WITHOUT `framework_stop_price`, and a `LIMIT` row WITH one,
    are both REJECTED (the second is the rejected-FTRE shape).
  - The idempotency digest is INJECTIVE: a `decline_reason` containing `|`, `:` and a digit run does not let
    two distinct decisions share a key.
  - **THE 0032-PRESERVATION SUITE:** re-run every assertion from `tests/data/test_migration_0032.py` against
    the post-`0033` `latch_view_events` — both identity-coherence triggers (bucket, evaluation identity,
    detection date, pipeline twin), every CHECK, the RESTRICT, and the state enum. **PLUS the §C.1.1
    STRENGTHENING, which is the one place the rebuilt table is deliberately STRICTER than `0032`:** the
    post-`0033` table REJECTS `'2026-99-99'` on `detection_date` and on `view_session_date`, where the shipped
    `0032` table ACCEPTS it. Assert the pre-`0033` acceptance too (against a v32 fixture DB), so the test
    proves the migration CHANGED something rather than merely that the new table is well-formed — a
    preservation suite that only re-runs `0032`'s own assertions would pass identically whether or not the
    correction landed.
  - **THE OTHER TWO REBUILD TESTS (§C.1 "the rebuild is mechanical", Codex R28 MAJOR)** — the preservation
    suite alone cannot catch the rebuild's two other failure modes: (i) `run_migrations` +
    `executescript` against a REAL v32 DB applies `0033` without error (catches syntax / unbalanced parens /
    unresolvable references — the class no prose review sees, and the plan's own DDL block carries
    PLACEHOLDERS, so a literal copy MUST fail this test); (ii) a CHECK-SET DIFF parsed from both DDLs, with
    whitespace normalised, whose symmetric difference equals EXACTLY the four enumerated deltas — catching an
    ADDED or silently-ALTERED constraint, which the preservation suite (known rejections only) and
    `executescript` (happy with any valid constraint) both miss. Plus the trigger-SQL equality check against
    `0032`'s bodies modulo the table name.
  - **The telemetry UNIQUE is `(candidate_id, view_session_date, surface)`** — asserted by PRAGMA
    introspection of the rebuilt table, plus a NEGATIVE assertion that nothing keys telemetry on
    `(evaluation_run_id, ticker, ...)`. Task 1's first draft still named the OLD tuple after §C.1 was re-keyed
    (Codex R17 MAJOR), which is exactly how an implementer following the task list undoes the bridge-key
    correction; introspection cannot drift from the prose the same way.
  - **NO two-surface INSERT test (Codex R17 MAJOR).** `CHECK (surface IN ('latch_panel'))` makes a second
    surface UNWRITABLE today, so a test inserting two surfaces cannot pass and the plan must not claim
    multi-surface admission its own enum forbids. The `surface` leg of the UNIQUE is proved by DDL
    INTROSPECTION plus a same-surface duplicate rejection; admitting a real second surface is a deliberate
    CHECK widening under the #11 discipline and is 21-F's decision (§C.1), not a fact this arc can demonstrate.
  - A pre-`0033` row survives the rebuild carrying `surface='latch_panel'` and ALL THREE actionability columns
    `= 0` (a backfill of `1` FAILS — R16 MAJOR 2).
  - **THE MONOTONICITY CHECKS PIN `ever`, AND ONLY `ever` (Codex R25 MAJOR).** Raw INSERTs:
    `(first=1, last=0, ever=1)` is **ACCEPTED** — it is the true record of an offered render followed by a
    withheld one (§C.1), and a test asserting it is rejected would re-impose the false invariant the third
    column was added to remove; `(first=0, last=1, ever=1)` is ACCEPTED (the reverse order);
    `(first=1, last=0, ever=0)` and `(first=0, last=1, ever=0)` are both **REJECTED** by
    `ever >= first` / `ever >= last` respectively. Four cells, because a test covering only the two
    rejections passes against a DDL that also forbids the legal pair.
  - The three-mirror agreement test, parsed from the migration SQL, for **EVERY enum CHECK in `0033`** —
    `intent_kind`, `surface`, `attested_disposition`, `validity_outcome`, `framework_order_type`,
    `actual_order_type`, `framework_duration`, `actual_duration`, `derivation_sizing_basis`,
    `latch_view_events.surface`, **and the JSON-expressed `validity_detail.$.broker_snapshot_branch`
    (Codex R28 MAJOR)**. **This prose list is ILLUSTRATIVE; the MANIFEST below is the authority and no count
    is stated anywhere** — the roster grew from four to ten to eleven across three rounds and each stated
    cardinality went stale on the next edit. That last one escaped the list for eleven rounds purely because it
    is written as a `json_extract(...) IN (...)` predicate rather than a column `CHECK (col IN (...))` — a
    difference in SYNTAX, not in kind, and exactly the shape of hole the #11 rule exists to close. It mirrors
    `LATCH_BROKER_SNAPSHOT_PERSISTED_BRANCHES`, and a SEPARATE assertion pins
    `LATCH_BROKER_SNAPSHOT_PERSISTED_BRANCHES < LATCH_BROKER_SNAPSHOT_RENDER_BRANCHES` as a STRICT subset —
    equality would mean the §C.2 narrowing had been silently undone.
    Each has a frozenset in `swing/latches/constants.py`, is validated in the
    dataclass `__post_init__`, and the test parses the migration SQL and asserts EXACT set equality for all of
    them, with `models.py`'s being the SAME OBJECT (`is`), not a copy. **Naming only a subset is how the #11
    rule gets violated while its own test passes** (R23 MAJOR — the draft named a subset; R28 found one the
    full list had still missed).
    **AN ANNOTATED MANIFEST, NOT A GREP AND NOT A PROSE COUNT (Codex R29 MAJOR).** "Grep every `IN (` list"
    fails in BOTH directions and the evidence is on disk: `grep -c "IN ("` on `0032` returns **0**, because
    its two latch-state enums wrap the line as `IN\n    ('armed',...)` — so the rule MISSES real enums — while
    on `0033` it MATCHES a pile of non-enum predicates (`intent_kind IN ('place','decline','validity')` and
    `intent_kind NOT IN (...)` are shape-exclusion subsets; `actual_order_type IN ('STOP_LIMIT','LIMIT')`
    inside the accepted-by-broker completeness CHECK is a restatement, not its own enum;
    `json_type(...) IN ('true','false')` is a SQLite type predicate). A prose count is no better — it was
    wrong twice.
    So Task 1 builds a **MANIFEST**: parse `0033` for every `IN`-list predicate (whitespace-normalised, so
    line-wrapped ones are found), and require EVERY entry to be classified as either
    **`MIRRORED`** — naming its Python frozenset and its dataclass validator — or **`NO_ENUM_MIRROR`** with a
    written reason. **An unclassified predicate FAILS the test.** That is what makes a twelfth enum fail
    rather than join the blind spot, and it is the same "annotate, never stay silent" shape the plan uses for
    every other exemption list. The two PRESERVED `latch_view_events` latch-state enums are classified
    `MIRRORED` against 21-A's existing `_LATCH_VIEW_STATES` constant (they are 0032's, still live in the
    rebuilt table, and excluding them by SILENCE is exactly the hole this replaces).
  - The backup-gate boundary matrix, all four cells: `(32,33,True)`, `(31,33,False)`, `(32,32,False)`,
    `(33,33,False)`. **The `(32,33,True)` cell is required** — without it a gate whose body is an
    unconditional `return` passes the whole test (the 21-A Codex R4-2 lesson).
  - `PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES == PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES |
    {"latch_view_events"}`.
  - `record_intent` idempotency: two calls with the same key return the same `intent_id` and leave ONE row.
  - `record_view(..., surface=..., actionable=...)` and `get_view(..., surface=...)` are REQUIRED kwargs (a
    call without raises `TypeError`); a same-surface replay -> ONE row `view_count=2`. **The three
    actionability columns, each asserted SEPARATELY across an offered-then-withheld replay** (`actionable=1`
    then `actionable=0` in one session): `actionable_at_first_view` stays `1`, `actionable_at_last_view`
    FALLS to `0`, `actionable_ever_viewed` stays `1`. This ordering is the discriminator — the reverse order
    (withheld then offered) passes under BOTH the correct rule and the superseded "advance last with MAX()"
    rule, so a test written only that way proves nothing. A second assertion in the reverse order pins that
    `actionable_ever_viewed` rises `0 -> 1` and never falls.
    **NO two-surface INSERT test at ANY level (Codex R18 MAJOR 4)** — the `surface` CHECK makes a
    second surface unwritable, so it cannot pass; the `surface` leg of the UNIQUE is proved by DDL
    introspection and real second-surface inserts belong to the future CHECK-widening migration (21-F's call).
  - A `validity` row requires BOTH `validity_outcome` and `validated_place_intent_id`, MAY carry the observed
    `actual_*` params (R17/R18 CRITICAL), and MAY NOT carry any `framework_*` / `derivation_*` value.
  - A `place` OR `decline` row MUST carry the complete framework order AND the whole drift-capable derivation
    block, and MUST NOT carry `actual_*` params (R18 MAJOR 7 — a decline is a decision ABOUT a prepared order,
    and erasing that order leaves RD unable to audit what was declined).
  - **THE FTRE DIVERGENCE INSERT, AS RAW SQL AGAINST THE REAL MIGRATION (R18 CRITICAL):** a `place` row
    (`LIMIT` / `GOOD_TILL_CANCEL` / **limit 18.89** — the cent-quantized cap per §D.1, NOT the raw 18.8902,
    so the fixture matches what the card shows and what the delta compares — / qty 9 / full derivation block)
    plus its `validity` child
    carrying observed `actual_order_type='LIMIT'`, `actual_limit_price=18.89`, `actual_quantity=10` — both
    rows must INSERT successfully — **the validity child carries `actual_duration='GOOD_TILL_CANCEL'` too**
    (R20 MAJOR: the agreement denominator needs a COMPLETE actual side, and an omitted duration makes
    `compute_order_delta` return `any_difference is None` (UNKNOWN) rather than a clean quantity mismatch, so
    FTRE would still miss the metric). **THE FIXTURE MUST BE COMPLETE OR IT CANNOT INSERT (Codex R25
    MAJOR).** An `accepted_by_broker` validity row is required by §C.2 to carry a non-blank
    `actual_broker_order_id` AND a full seven-key `validity_detail` envelope, and the child here also inherits
    the parent's `action_session_date` (the trigger's session leg). An earlier revision of this bullet listed
    only the four `actual_*` order fields — written literally it FAILS against the correct schema, and the
    tempting repair is to weaken the CHECKs rather than complete the fixture. So the fixture states, concretely:
    `actual_broker_order_id='1002937461'`, `action_session_date` = the parent place row's, and a
    `validity_detail` object carrying every roster key with valid shapes (`broker_snapshot_ts` a
    `T`-separated 19-char stamp, `broker_snapshot_branch='presence'`, a 64-char lowercase-hex
    `broker_snapshot_digest`, a round-trip-valid `broker_snapshot_session`,
    `attributable_order_count=1`, `exact_framework_match_count=0`, `indeterminate=false`). Note
    `exact_framework_match_count` is **0**, not 1 — that is the whole point of FTRE: the order is
    ATTRIBUTABLE to the latch and does NOT match the framework params, and a fixture that set it to 1 would
    quietly re-assert the exact-match gate R17 removed.
    The test asserts the denominator gains 1 and the numerator does not.
    The R17 fix was described in prose while the CHECK still forbade it; a
    raw-SQL migration test (not merely a repo/model test) is what makes that impossible to repeat.
  - `ACTIONABLE_VIEW_SURFACES <= LATCH_VIEW_SURFACES`, and both equal `{"latch_panel"}` today (section E.3).
**THE CONSTRAINT SET WAS EMPIRICALLY AUDITED, NOT JUST REVIEWED — ZERO GAPS (orchestrator-directed,
post-round-29; the probe and surface counts below are a DATED MEASUREMENT of that run, not a live invariant,
and Task 1 REGENERATES the matrix from the schema rather than reproducing these numbers).** Both tables were BUILT AS REAL SQLITE and probed constraint by constraint:
`latch_order_intents` extracted verbatim from §C.2's DDL (**it EXECUTES**), and `latch_view_events`
reconstructed exactly as §C.1's mechanical procedure directs — 0032's preserved CHECKs plus the deltas —
which **also EXECUTES, and whose CHECK set matched what §C.1's oracle computes**, independently corroborating
that oracle. (At the time of the run: 38 columns / 48 CHECKs and 16 CHECKs respectively — recorded as
evidence the probe was real, NOT as figures any test should assert.) Every constraint rejected what the plan says it rejects
and accepted what the plan says it accepts, including both DELIBERATE accepts (`derivation_real_equity` at
zero and negative; `first=1, last=0, ever=1`) and all three triggers plus `UNIQUE(idempotency_key)`.

**The audit matrix IS Task 1's test oracle — reproduce it, do not re-derive it.** The full per-probe table is
in `.copowers-findings.md` under "SYSTEMATIC CHECK/TRIGGER AUDIT". Two disciplines it encodes, both learned
the expensive way in this arc:
- **A CHECK passes when its expression is NULL**, so any guard built from a function that returns NULL on bad
  input silently admits exactly what it was written to reject. Probe it; never reason about it.
- **A comment claiming a guarantee is not a guarantee.** `0032`'s comment argued carefully for round-trip
  equality OVER `IS NOT NULL` — correct about normalisation, wrong that normalisation was the whole space
  (§C.1.1). When a constraint's comment explains why it is sufficient, treat that as a HYPOTHESIS TO PROBE.

- [ ] **Step 2:** implement. Backup gate copied VERBATIM from `_phase21_arc_a_backup_gate`. Repo functions
      issue NO BEGIN/COMMIT (the route owns `with conn:`).
- [ ] **Step 3:** `python -m pytest tests/data -q` green; commit
      `feat(data): Task 1 — migration 0033 latch_order_intents + the telemetry surface column`.

### Task 2: `swing/latches/order_intent.py` — the prepared order + the delta (PURE)

- [ ] Failing tests from the REAL FTRE geometry: pullback regime -> `LIMIT` / `stop_price is None` / limit
      18.89 / **9 shares**, with the full `OrderDerivation` asserted field by field; breakout regime (a close
      below 18.34) -> `STOP_LIMIT` / stop 18.34 / limit 18.89 / 9 shares. `regime_order_type is None` ->
      `order is None` + `withheld_reason == 'regime_undeterminable'` + a non-empty `withheld_detail`.
      Infeasible sizing -> `withheld_reason == 'sizing_infeasible'`. `PreparedOrderResult.__post_init__`
      rejects both-None and both-set (a lossy result type is what R3 MAJOR 4 was about).
      **The A.2 discriminator:** a test asserts the qty is derived from
      the LIMIT and computes 9 — a pivot-based implementation returns 10 and FAILS.
      `compute_order_delta` cell tests: exact match (all deltas 0/False); FTRE framework `LIMIT 18.89 / 9` vs
      actual `LIMIT 18.89 / 10` -> `quantity_delta == 1`, every other field equal, `any_difference is True`;
      a missing actual side -> `None` (UNKNOWN), never `False`; a `18.885` vs `18.89` compare -> equal at 2dp.
      **`canonical_duration` parity (R19 MAJOR 8):** `GTC` and `GOOD_TILL_CANCEL` compare EQUAL and an
      unmapped duration canonicalises to `UNKNOWN` and compares as UNKNOWN, never as agreement (a raw-string
      comparison reports a duration divergence on FTRE's semantically identical order and FAILS).
      **The stop-leg tri-state, all three cells:** pullback framework with no stop leg vs an actual with no
      stop leg -> `stop_leg == 'both_absent'`, `stop_price_delta is None`, contributing MATCH to
      `any_difference` (a bare `float | None` implementation reports UNKNOWN here, and unknown is never
      agreement, so the CORRECT order scores as a non-match — it FAILS); both present -> `'compared'` with the
      signed delta; exactly one present -> `'unknown'` and `any_difference is None`.
- [ ] Implement; commit `feat(latches): Task 2 — the prepared-order derivation + the per-field delta`.

### Task 3: `swing/latches/classification.py` — dispositions (PURE)

- [ ] Failing tests: **the §E.0 properties FIRST** — totality over the key product; the monotone property
      asserted THROUGH `classify_latch` on concrete full / partial / none substrates (NOT over the table's
      sentinel values, which prove nothing about the final disposition — R19 MAJOR 5); and the behavioural
      no-re-derivation check that the classifier's output depends on nothing the `CoverageVerdict` does not
      carry. Then every §E precedence rung; `prompt_required` over every member of `LATCH_DISPOSITIONS` (exactly one True,
      and it is `discipline_lapse`); the unattested-terminal-viewed cell's
      `effective_disposition == "discipline_lapse"`; the coverage arithmetic at all four boundaries
      (anchor == epoch, anchor == epoch - 1 session, clear == epoch, clear == epoch + 1 session); a view row
      dated inside the window but recorded against a TERMINAL state is NOT evidence (§E.3).
- [ ] **THE COVERAGE / ACTIONABILITY MATRIX — all four cells, exactly as §E states them once.** Each cell
      discriminates a different wrong implementation:
      - FULL + no awareness -> `away_unseen`.
      - FULL + awareness + only `actionable_ever_viewed = 0` rows -> `never_actionable` (an implementation
        ignoring the column returns `discipline_lapse` or `away_unseen` and FAILS, in opposite directions).
      - PARTIAL + awareness + only `actionable_ever_viewed = 0` rows -> `never_actionable` (an implementation
        re-applying a coverage veto after the table routed normally returns `pre_telemetry` and FAILS).
      - PARTIAL + NO awareness -> `pre_telemetry` — the FTRE geometry (an implementation ranking actionability
        above coverage flips the arc's headline case on the first page view and FAILS).
- [ ] **The ordering test:** PARTIAL + no awareness with `broken` telemetry health STILL returns
      `pre_telemetry`, NOT `telemetry_unhealthy` — health may not pre-empt RD's ruled table.
- [ ] **The two-axis separation** — a `place` intent whose governing `validity` row says
      `rejected_by_broker` yields `disposition='accepted'` AND `execution_outcome='rejected_by_broker'`, and
      an unobserved validity yields `unknown`, never a success value (an implementation collapsing the axes
      returns a clean `accepted` and FAILS both).
- [ ] **The §F.3 resolver precedence** — a mis-attested `not_submitted` on a latch the derivation cleared as
      `fill` still resolves `accepted_by_broker` (rung 2 beats rung 3); a fill dated BEFORE the place intent
      does NOT vouch for it; and **the parent scoping** — place -> `rejected_by_broker` -> re-place -> fill
      leaves the FIRST place at `rejected_by_broker` and resolves only the SECOND as `accepted_by_broker`
      (a latch-scoped fill rung rewrites the first and FAILS).
- [ ] Implement; commit `feat(latches): Task 3 — the three-state disposition classifier`.

### Task 4: THE FTRE COVERAGE TESTS (§A.1.4) — RD RULED 2026-07-28; NO GATE REMAINS

**The gate is CLOSED** (§A.1.5): RD ruled, the losing branch is deleted, and there is ONE expectation — FTRE
classifies `pre_telemetry` and its +1.22R lands in `unattributable_r`. No task in this plan is blocked
(Codex R18 MAJOR 3 — the gate prose outlived the gate).

- [ ] `tests/latches/test_ftre_coverage.py` implementing T-A, T-A2, T-B and T-C exactly as §A.1.4 specifies,
      on the real FTRE numbers (`candidate_id=11261`, eval run 121,
      pivot 18.34, stop 14.88, anchor 2026-07-20, horizon 2026-08-31, epoch 2026-07-29). Each test carries a
      docstring stating what a naive implementation does and why that fails here.
- [ ] Commit `test(latches): Task 4 — the FTRE coverage triple (vacuity detector + away + lapse)`.

### Task 5: telemetry health + the away rate + the parity report (PURE)

- [ ] **THE BUCKET PARTITION IS OVER CELLS, NOT OVER DISPOSITIONS (§F.3), + THE GUARD RD SINGLED OUT.** The
      test walks the FULL `(disposition, is_terminal)` PRODUCT — all `2 x len(LATCH_DISPOSITIONS)` cells —
      and asserts: every COHERENT cell maps to exactly one of the five buckets; the one INCOHERENT cell
      `("pending_live", True)` RAISES; and the five bucket sums reconcile to the corpus total.
      **A test phrased as "every member of `LATCH_DISPOSITIONS` appears in exactly one of the five sets" is
      FORBIDDEN** — since the terminality gate landed, `accepted` is `decision_r` when terminal and
      `pending_r` when not, so that assertion is either false or silently re-pinning the pre-gate model
      (R24 MAJOR). Plus **`r_bucket_for` RAISES on a disposition absent from the RULED UNION, under BOTH
      terminality values (Codex R25 MAJOR)** — a test adds a fake disposition to `LATCH_DISPOSITIONS` ONLY
      (not to any bucket set) and asserts the raise for `is_terminal=True` AND for `is_terminal=False`.
      **The `False` case is the load-bearing one and an earlier revision of this bullet explicitly skipped
      it**, reasoning that the terminality gate would return `pending_r` first — which is not a reason to
      omit the test, it is the DEFECT the test detects (a default relocated, not removed). Plus
      `_RULED_DISPOSITIONS == LATCH_DISPOSITIONS` as its own assertion, so a disposition added to the enum
      without a bucket ruling fails at import-adjacent test time rather than being scored. **Do not
      reintroduce a fallthrough, and do not weaken the `is_terminal=False` case, to make these pass.**
- [ ] **RULING 1 — `pending_live` is REPORTED, NEVER SCORED, and TERMINALITY IS A GATE.** It lands in
      `pending_r` with its own count and enters NO denominator (decision, away, discipline alike). Two test
      groups, because the second is the one a disposition-only implementation fails:
      - both away rates computed over a corpus WITH and WITHOUT an added `pending_live` latch are
        IDENTICAL — an implementation that lets it into the denominator moves them and FAILS;
      - **the five NON-TERMINAL cells the R23 CRITICAL named** — a LIVE latch with (a) a `place` intent,
        (b) a `decline` intent, (c) an `attest` intent, (d) no views at all, (e) withheld-only views — each
        buckets to `pending_r` and leaves every rate and every R total UNCHANGED. A `r_bucket_for` taking only
        a disposition scores these as `accepted` / `declined` / `attested_*` / `away_unseen` /
        `never_actionable` respectively and FAILS all five.
- [ ] **RULING 2 — `attested_was_away` is a THIRD terminal category.** It lands in `attested_away_r`, NOT
      `decision_r` and NOT `away_r`; it IS in `classifiable_fires`; it is EXCLUDED from the discipline signal.
      The **objective** rate counts `away_unseen` only; the **attested** rate counts
      `away_unseen + attested_was_away` over the SAME denominator; `attested_rate >= objective_rate` whenever
      both are non-`None`. A corpus with one of each discriminates all three wrong implementations
      (merged-into-away, left-in-decision, computed-over-different-denominators).
- [ ] Failing tests: the three counters incl. `uninstrumented_sessions`; `broken` at/above threshold and
      `indeterminate` below it; `AwayRateResult` cannot be constructed without `health`; **BOTH rates are
      `None`** and a populated `withheld_reason` under `broken`; the away-rate DENOMINATOR excludes
      `pre_telemetry`, `never_actionable`, `telemetry_unhealthy` AND `pending_live`;
      **`covered = 1, uncovered >= threshold` verdicts `broken`, not `ok`** (R19 MAJOR 6 — under the draft's
      `covered == 0` rule that substrate verdicts `ok` and the latch reaches `away_unseen`, so the cell
      discriminates); FTRE's +1.22R landing in `unattributable_r` per RD's ruling; **the agreement rate's four
      counts** — a delta-clean place intent that the broker REJECTED is in neither the numerator nor the
      denominator and appears in `validity_failed`; an unobserved validity appears in `validity_unknown`, not
      in agreement.
- [ ] Implement; commit `feat(latches): Task 5 — the telemetry-health gate + the execution-parity report`.

### Task 6: the panel VM — the prepared-order block, the disposition, the prompt

- [ ] Failing tests: the offered form's VM carries every derivation line; the withheld form carries the reason
      and NO order numbers presented as a mandate; the attestation prompt renders only on
      `discipline_lapse`; the
      hidden-anchor payload is complete and its digest is stable; new `LatchPanelVM` fields are in
      `PANEL_SPECIFIC_FIELDS` (assert `declared_banner_fields()` is unchanged from 21-A); A6 — every new read
      degrades and the panel never 500s.
- [ ] Also: **the non-counted-surface property, exercised through the `counted_surfaces=` PARAMETER over a
      VALID `latch_panel` row (§E.3 conjunct 2, Codex R26 MAJOR).** An earlier revision of this bullet asked
      for "a view row on a surface NOT in `ACTIONABLE_VIEW_SURFACES`" — which is UNWRITABLE today
      (`CHECK (surface IN ('latch_panel'))` plus the model validator), so a literal implementer would have to
      bypass the very #11 mirror the test is meant to respect, or write a test that cannot pass. §E.3 already
      ruled this and Task 6 had not been brought into line. So: call the panel's `_load_views` and the pure
      classifier with `counted_surfaces=frozenset()` over a real `latch_panel` row and assert it appears in
      NO telemetry echo and moves NO disposition — the same property, no invalid fixture. Real
      second-surface rows belong to 21-F's CHECK-widening migration. Also: the beacon payload carries
      `actionable_candidate_ids` and `withheld_candidate_ids` SEPARATELY, and a withheld card's id is never in
      the actionable list (the R7 CRITICAL discriminator — on today's live substrate EVERY card is withheld,
      so a payload that lumps them records a false view for every latch); and the beacon persists the
      RENDER-TIME `actionable` claim even when the POST-time re-derivation now disagrees, logging a warning
      instead of downgrading it (the R11 MAJOR 3 discriminator — a weaker-claim implementation manufactures a
      `never_actionable` for a mandate the operator was genuinely shown).
- [ ] Implement; commit `feat(web): Task 6 — the prepared-order panel view model`.

### Task 6b: the beacon-route rewrite (`POST /latches/view`)

**GATE ON THIS BEING ITS OWN STEP:** the R7 `actionable` column, the R11 render-time rule and the §C.1 payload
split are all inert until this handler changes. Left as a footnote on another task it is exactly the kind of
step that gets absorbed and skipped.

- [ ] Failing tests: the payload split parses; an id present in BOTH lists -> `400` naming the field; the
      200-id cap applies to the UNION; each list is intersected with the anchor-session live set INDEPENDENTLY;
      `record_view` receives `actionable=1` for actionable ids and `actionable=0` for withheld ids;
      `actionable_at_first_view` never changes on a second POST, `actionable_at_last_view` takes the SECOND
      POST's own value (including falling `1 -> 0` on an offered-then-withheld pair), and
      `actionable_ever_viewed` advances `0 -> 1` and never `1 -> 0`; the four-tier session-anchor ladder and the `409` stale notice still behave
      exactly as 21-A shipped them (a no-regression lock on the shipped route).
- [ ] Implement; commit `feat(web): Task 6b — the beacon records surface + render-time actionability`.

### Task 7: `POST /latches/intent` + the templates

- [ ] Failing tests, incl. the `validity` prompt path: a `place` intent from an EARLIER session with no
      matching resting order at the broker renders the ABSENCE prompt (from the ORDER FRAGMENT, not from the
      panel GET) with NOTHING pre-selected and with an
      option set EQUAL to `LATCH_VALIDITY_OUTCOMES` minus `accepted_by_broker` (no "filled" option — the R7
      MAJOR 2 discriminator); a latch cleared by FILL renders NO validity prompt at all and derives
      `accepted_by_broker` from the fill; **`resolution.kind != "ok"` renders NO validity prompt in either
      direction** (the R8 MAJOR 1 degraded branch — a prompt built on an unknown order book is a prompt whose
      answer the operator would infer from the panel's own silence); the intent path still makes ZERO
      `borrow` calls with the prompt in play; `attributable_order_count > 1` or an indeterminate status renders the
      existing multiplicity / indeterminate note and NO validity prompt; a `validity` POST whose
      `broker_snapshot_ts` is from a prior action session or older than
      `LATCH_BROKER_SNAPSHOT_MAX_AGE_SECONDS` -> `409` with ZERO rows written;
      **THE DIVERGENCE PATH, which is the arc's own worked example (R17 CRITICAL):** a latch whose framework
      order is `LIMIT 18.89 / 9 sh` with an attributable resting order of `LIMIT 18.89 / 10 sh` RENDERS the
      validity prompt (an exact-match gate renders nothing and FAILS), the prompt NAMES the difference, and
      confirming writes ONE `validity` row carrying the OBSERVED `actual_*` params so `compute_order_delta`
      yields `quantity_delta == 1` FROM THE LEDGER rather than from a fixture; **that divergent row carries
      `validity_outcome='accepted_by_broker'` and therefore ENTERS the agreement DENOMINATOR while FAILING the
      numerator** (R19 MAJOR 7 — an `unknown` outcome leaves FTRE visible as a delta yet excluded from the
      metric it exists to feed); a `validity` row written without the snapshot envelope in `validity_detail`
      is REJECTED (R19 MAJOR); the fragment emits ONE `broker_snapshot_json` hidden field whose key set EQUALS
      what `validity_detail` requires (R20 MAJOR — drift between the two makes the audit row unwritable) and
      the handler persists it VERBATIM without synthesising any key; two validity answers differing only as
      `GTC` vs `GOOD_TILL_CANCEL` produce the SAME idempotency key and ONE row (R20 MAJOR);
      the `broker_snapshot_digest` CHANGES when a non-matching resting order appears while
      `attributable_order_count` stays 0 (a counts-only digest is identical across those two books and FAILS) and
      is UNCHANGED across a reload showing the same book; a `place`
      intent WITH an ATTRIBUTABLE resting order AND `attributable_order_count == 1` AND not indeterminate renders the
      PRESENCE prompt with `accepted_by_broker` pre-selected
      and the observed `order_id` carried (the R5 CRITICAL discriminator — an absence-only implementation
      renders no prompt here and the agreement numerator stays permanently zero); no `validity` row is EVER
      written without a POST; answering writes ONE `validity` row carrying `validated_place_intent_id` = THAT place
      intent, and only that place intent's `execution_outcome` moves off `unknown`; a SECOND place/validity
      cycle on the same latch does NOT rewrite the first cycle's reported outcome (the R4 MAJOR 3
      discriminator — a latest-validity-row-by-latch read FAILS this); the panel never ASSERTS a validity
      outcome from the absence alone.
- [ ] Failing tests: `GET` -> 405; the four-tier session-anchor ladder (each rung's status + the named field);
      a mutated `framework_limit_price` -> 409 naming the field, ZERO rows written; a double POST -> ONE row,
      same `intent_id`, `200` both times; a `decline` with a blank reason -> 400; a `cancel` with no order id
      -> 400; the form carries `hx-headers` with `HX-Request` and `hx-target="this"`; the response fragment
      root is not a `<tr>`; **no Schwab call is made on any path** (assert `schwab_api_calls` row count is
      unchanged across the POST).
- [ ] **The §G.1 ordering tests, which are the ones a naive handler fails:** (a) POST once, then advance the
      clock so the anchor is more than one session stale, then REPLAY the identical payload -> `200` + the
      same `intent_id`, **NOT** `409` (step 4 precedes step 5); (b) a NEW intent with that same stale anchor
      -> `409` (step 5 still binds for a first insert); (c) simulate the lost race by pre-inserting the row
      between the handler's step-4 SELECT and its step-6 INSERT (monkeypatch the seam) -> `200` returning the
      pre-inserted row, ZERO `IntegrityError`, ONE row total.
- [ ] **THE KIND-SCOPED KEY TESTS (§G.1, Codex R25 + R26 MAJOR) — both components, both directions:**
      (d) **the validity next-session replay** — answer a `validity` prompt, then re-render the fragment in a
      LATER action session and resubmit the SAME answer for the SAME parent: **ONE row, `200`, the same
      `intent_id`.** This is the test that fails against EITHER half-fix — an implementation keying the
      session component off the current anchor writes a second row, and so does one that scopes
      `session_component` but leaves `view_session_date` inside `anchor_digest`.
      (e) **the discrimination that must SURVIVE the scoping** — two `validity` answers differing ONLY by
      `validity_outcome`, and two differing ONLY by `validated_place_intent_id`, produce DISTINCT keys and
      TWO rows. Without (e), (d) passes trivially against a key that has stopped discriminating at all.
      (f) **the decision kinds are UNCHANGED** — the same `place` decision submitted in two different
      sessions still produces TWO rows, and a mutated `framework_limit_price` still changes the key
      (the R5 laundering defence is intact for the kinds that actually submit a framework anchor).
- [ ] Also: the rendered base still carries the `htmx.config.responseHandling` 4xx-swap override (without it
      the 400/409 fragments are invisible in a browser and the endpoint silently loses its error surface).
- [ ] Implement; commit `feat(web): Task 7 — POST /latches/intent (log-only) + the prepared-order form`.

### Task 8: B6 — the separated-claims construction

- [ ] Failing tests per §H (the zero-case must not contain `"among the 0"`).
- [ ] Implement; commit `fix(web): Task 8 — separated alarm/form-check claims (B6)`.

### Task 9: `swing latches parity` — the monthly read

- [ ] **BOTH AWAY RATES, LABELLED, ON ADJACENT LINES** (RD ruling 2): `OBJECTIVE (primary)` and
      `ATTESTED (upper bound)`. Stage-3 auto-place must not be able to take the decision quietly on the larger
      number, so a report printing only one rate, or printing them unlabelled, FAILS. Both print the health
      verdict on the SAME line and both print `WITHHELD` (with the counters) under `broken`.
- [ ] **`pending_r` printed as its own visible line** (RD ruling 1) so the reader sees the pipeline rather
      than a silently smaller corpus, and a test asserts it is NOT folded into any rate's denominator.
- [ ] **`decision_r`'s three evidence-kind sub-counts printed** — `decision_r_logged` / `decision_r_attested`
      / `decision_r_inferred` — alongside the total (§A.0: the sum may be reported, the distinction may not be
      erased). A test asserts the three sum to `decision_r` and that all four appear in the output.
- [ ] Failing tests: the report prints the disposition histogram, the agreement rate, the per-field delta
      totals; the `--since` cutoff filters on `recorded_ts` and NOT on `action_session_date` (the R9 MAJOR 2
      discriminator: a validity row recorded in month N about a month-N-1 render belongs to month N); the FIVE
      bucket counts and the exclusion counts (`pre_telemetry` / `never_actionable` / `telemetry_unhealthy`);
      `inferred_origin` per resting order — labelled as INFERRED except where a captured broker order id makes
      it exact (a report printing a bare `origin` FAILS); ASCII-only output verified through a real PowerShell
      subprocess (the cp1252 gotcha — `capsys` cannot see it).
- [ ] Implement; commit `feat(cli): Task 9 — swing latches parity, the monthly execution-parity read`.

### Task 10: the BEHAVIOURAL no-write pin + CSS + nav

- [ ] The pin of the Global Constraints section, **in that order and with (i) FIRST because it is the
      PRIMARY enforcement (R24 MAJOR — this task previously OPENED with the introspection sweep, which ships
      the exact renamed-mutator hole (i) exists to close):**
      **(i) TRANSPORT-LEVEL, DENY-BY-DEFAULT** — a stub over the session schwabdev issues requests through
      that FAILS ON ANY NON-GET to the Schwab Trader API host, driven over `GET /latches`, every
      `POST /latches/intent` branch and `POST /latches/orders`. Names cannot matter, so a renamed or
      newly-added mutator is caught regardless of what it is called.
      **(i-b)** the deny-by-default schwabdev-callable sweep against an EXPLICIT read-only allowlist
      (secondary net). **(ii)** the zero-`borrow` seam assertion on the intent path. **(iii)** the
      `schwab_api_calls` row-count invariant. **(iv)** the grep belt, explicitly NOT the enforcement.
      **(v)** the bare name `matched_order_count` appears NOWHERE in 21-B's own code or tests (21-A's
      `LatchOrderJoin` field keeps its name; every 21-B consumer must name which question it asks).
      CSS tokens under `:root` + `body.dark`, `var()`-only.
- [ ] Commit `test(latches): Task 10 — behavioural pin of ZERO Schwab writes + the panel style tokens`.

---

## K. Tests that actually discriminate

### K.1 The FTRE triple — what each one would catch

| test | passes today | what breaks it |
|---|---|---|
| **T-A** real-data anchor (RD ruling 3) | asserts `pre_telemetry` on the real zero-row substrate + the +1.22R out of both scored buckets | ANY implementation mapping "no view rows -> away". |
| **T-A2** stability property (RD ruling 2) | a view row added to the covered portion moves FTRE off `pre_telemetry` ONLY into an awareness-established cell | an implementation that re-reads coverage as "we have rows now" flips it to `away_unseen` |
| **T-B** seeded discriminating test (RD ruling 3) | asserts `away_unseen` on a FULLY-covered window with a live-beacon witness | removing the sibling view rows flips it to `telemetry_unhealthy`; moving the anchor one session before the epoch flips it to `pre_telemetry` |
| **T-C** pessimistic default | asserts `discipline_lapse` | adding a single view row to T-B produces T-C, and deleting it reverses — the viewed/never-viewed discriminator |

### K.2 The other named acceptance items (brief §3)

- **Each of the four classification cells** — §E rungs 1, 2, 6-terminal, 7-full.
- **The prompt fires ONLY on viewed=YES + no-action and never elsewhere** — the eleven-disposition parametrised
  sweep (§E.2).
- **An unattested ambiguous cell defaults to LAPSE** — §E.1, asserted on `effective_disposition`.
- **A double-click yields ONE logged intent** — Task 7, asserting the row count AND that both responses carry
  the same `intent_id`.
- **A stale-anchor POST is REFUSED rather than silently recomputed** — Task 7, asserting `409` AND zero rows.
- **The per-field delta against a real geometry** — Task 2: framework `LIMIT 18.89 / GTC / 9` vs FTRE's actual
  resting `GTC LIMIT 18.89`, giving a clean single-field quantity delta.

### K.3 Arithmetic verified under BOTH paths (the regression-arithmetic discipline)

| assertion | pre-fix value | post-fix value | discriminates? |
|---|---|---|---|
| FTRE prepared qty | 10 (pivot basis, `build_recommendations`) | **9** (limit basis) | YES |
| FTRE disposition, zero telemetry | `away_unseen` (naive) | **`pre_telemetry`** (RD ruling 2) | YES |
| all-clear zero-case | `"No alarms among the 0 latches form-checked."` | **`"No alarms."`** | YES |
| FTRE regime today (derivation session 2026-07-28, newest close dated 2026-07-27) | — | **`None` -> form WITHHELD** | YES (a form that renders is a bug) |

---

## L. Gates

1. **RD plan-stage review — BLOCKING.** §A.1 (the acceptance-test resolution and the third bucket), §A.2 (the
   sizing basis), §A.3 (computed-not-stored delta), §C.2 (the ledger shape), §E (the classification semantics
   and the pessimistic default), §F (the telemetry-health gate). **§A.1 and §A.1.6 are RULED and no longer block** (R24 MAJOR — this
   line contradicted §A.1.5's "nothing is gate-blocked now"); **§A.2 (the sizing basis) and §A.3
   (computed-not-stored delta) remain OPEN and are the only RD items still outstanding.**
2. **CHARC** — §C.1's rebuild-vs-ALTER choice and the 33-column table against B7's "minimal".
3. **review-strong to convergence** + **codex-auto-review (REQUIRED, charter §2.9)** — and per the recipe,
   VERIFY the working invocation at dispatch and report which form ran. On this worktree
   `codex exec review` fails with `Not inside a trusted directory` and has no `--skip-git-repo-check`; the
   COLD-AUDIT form (`codex exec -s read-only -c model_reasoning_effort=high`, reading the changed files
   directly) is the canonical worktree invocation.
4. **Suite + ruff + merged-head no-false-green.**
5. **BINDING operator GUI witness, BOTH states:**
   - **State A — form WITHHELD.** Today's substrate: regime undeterminable, the mandate facts render, the
     reason renders, **no ACCEPT button exists in the DOM**.
   - **State B — form OFFERED.** Reached via a reversible seed helper (the 20-C precedent) that supplies a
     derivation-session close: the full derivation renders; ACCEPT logs ONE intent; a double-click still logs
     ONE; DECLINE without a reason is refused; a stale anchor shows the reload notice.
   - HTMX form surfaces are browser-only (the `hx-headers` 403 and the 204-vs-303 classes) — TestClient cannot
     see them, so this witness is binding, not confirmatory.
6. **Merge + live migration as ONE atomic operator-authorized step**, held clear of the 17:30 window, with the
   exact-match v32 guard (`current_version == 32`).
7. **Ordering:** 21-G merges FIRST (§B). If 21-B is ready first it waits.
8. **Gate visibility (harness-architecture §2):** if the merge proceeds with any director gate outstanding, the
   merge report says so in one clause.
9. The ORCHESTRATOR posts the return to `charc,rd` after its QA. The implementer posts nothing.

---

## M. Known limitations + banked V2

1. **Every live latch is `pre_telemetry` today** (§A.1.2). The instrument's first
   fully-classifiable observation is the next A+ fire on or after 2026-07-29.
2. **The telemetry-health check is one-sided** (§F.1): it cannot separate a dead beacon from a genuinely absent
   operator. V2: give `POST /latches/orders` its own `schwab_api_calls` surface value so a panel render is
   attributable, making the check two-sided.
3. **Two identical decisions in one session collapse to one ledger row** (§G.1). The ledger records decisions,
   not clicks.
4. **Framework-vs-operator distinguishability is INFERRED, not tagged** (§G.4) — the report's field is
   literally named `inferred_origin`, and two identical orders are indistinguishable by params. Exact only
   where a broker order id was captured on a `cancel` or `validity` row. A broker-side client order id is a
   21-C dependency.
5. **`validity_outcome` is only ever set by the operator answering the validity prompt** (§F.3), and the
   prompt requires his click in BOTH the presence and the absence branch. So `validity_unknown` will dominate
   the first months and the report says so on the same line as the agreement rate. Stage 2's `preview_order` is what makes validity automatic — and eliminates the class entirely.
6. **The sizing-basis divergence with `build_recommendations` is flagged, not fixed** (§A.2). Reconciling the
   nightly briefing is a measurement-chain edit for a later arc.
6b. **A server-signed broker-context token is BANKED, not shipped** (§F.3). V1 bounds the SNAPSHOT AGE, which
   covers the realistic failure (an honest answer about a stale view); it does not defend against a FORGED
   local POST, because on a `127.0.0.1` single-operator app that threat implies an attacker who can already
   write the DB directly, where a token protects nothing. Revisit the moment the app leaves localhost.
7. **`POST /trades/sizing-hint` uses UNFLOORED equity** while every other sizing surface uses the floored
   figure (§D.2). Pre-existing, outside this arc, flagged.
8. **Base-break invalidation is still out of V1** (21-A §G.5). The prepared-order form inherits the
   stop-level-only qualifier and repeats it — it must not imply coverage the derivation does not have.
9. **The `date(x) = x` CHECK class is fixed HERE and audited ELSEWHERE** (§C.1.1). This arc corrects the only
   two occurrences in `swing/data/migrations/`, both in `0032`'s `latch_view_events`, because it rebuilds that
   table anyway. Whether NEAR-MISS variants of the same class exist in other shipped date/timestamp CHECKs is
   an audit the ORCHESTRATOR owns and this arc does not perform. The standing condition stands: a new
   `latch_view_events` writer landing before 21-B means the CHECK fix ships first, separately.
