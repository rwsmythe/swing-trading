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
`latch_view_events` to add `surface` + the two actionability columns and re-key its UNIQUE onto the bridge key. The web layer extends the EXISTING panel VM/route/template (no new base-layout VM field)
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
  and `actionable_at_first_view` / `actionable_at_last_view` fields on `LatchViewEvent`, and the
  `swing/data/db.py` version bump + backup gate) are the scoped
  addition the 21-B brief's SCHEMA TRIPWIRE authorizes — the same carve-out 21-A took for `0032`.
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
| zone cap 18.8902 | 4.0102 | **9** | 9 x 4.0102 = $36.09 = 0.481% — within the cap in every fill outcome |

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
```

- `1` — the latch's mandate was rendered in a form sufficient to act on (the prepared-order form was OFFERED).
- `0` — the latch's card rendered, but its prepared order was WITHHELD, so no decision was presented.

**TWO columns, not one, and they mirror the idiom `0032` already uses (Codex R13 MAJOR 2).** A single
`actionable` advanced by `MAX(existing, new)` would let an 18:00 offered render retroactively upgrade an 09:00
withheld one — while the row still carries `first_viewed_ts = 09:00`, so the record would assert "first viewed
at 09:00, with an actionable mandate", which is false. That is the stored fact depending on a LATER reload,
which is the same class of dishonesty as the R11 downgrade in the other direction. The fix is the shape the
table already uses for `latch_state_at_first_view` / `latch_state_at_last_view`: `..._at_first_view` is
IMMUTABLE after insert, `..._at_last_view` advances monotonically `0 -> 1` (never back). No new grain, no new
row, both facts preserved, and each timestamp keeps its own truthful companion.

**Classification reads `actionable_ever_viewed = 1`** as "the mandate WAS actionably presented in this
session" (§E.3) — the honestly-named column for that question. The `..._at_first_view` / `..._at_last_view`
pair stay literally true of their own views and exist so the record cannot lie about either timestamp's
companion fact.

Consumers, each distinct (§E.3, §F.1):
- the away/lapse split counts **only rows with `actionable_at_last_view = 1`** as a view;
- a latch with only `actionable_at_last_view = 0` rows across its whole armed window classifies
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
    -- value, so a raw INSERT could store first=1 / last=0 -- a row the dataclass
    -- REJECTS, i.e. the DB holding a shape the read path cannot hydrate, which
    -- is the dangerous asymmetry direction the #11 discipline exists to stop.

    -- Every 0032 CHECK reproduced -- WITH the R24 CRITICAL `IS NOT NULL`
    -- correction applied to both date CHECKs. 0032 as SHIPPED writes
    -- `date(detection_date) = detection_date` with no IS NOT NULL, which a
    -- length-correct invalid date such as '2026-99-99' passes (a SQLite CHECK
    -- passes on a NULL expression). This rebuild is the moment that is fixable
    -- for `latch_view_events` at zero cost, so it is fixed here; the SHIPPED
    -- table's exposure is a SEPARATE 21-A finding flagged to the orchestrator,
    -- not silently patched by this arc.
    CHECK (length(detection_date) = 10
           AND date(detection_date) IS NOT NULL
           AND date(detection_date) = detection_date),
    CHECK (length(view_session_date) = 10
           AND date(view_session_date) IS NOT NULL
           AND date(view_session_date) = view_session_date),
    ... every remaining 0032 CHECK reproduced VERBATIM ...
    -- The grain stays (latch, session, surface). Actionability is an ATTRIBUTE
    -- of that row, not part of its key: within one session a card can flip from
    -- withheld to offered when the nightly lands, so the LAST-view column
    -- advances 0 -> 1 monotonically while the FIRST-view column never moves.
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
INSERT INTO latch_view_events_new
    SELECT view_event_id, candidate_id, evaluation_run_id, ticker, detection_date,
           pipeline_run_id, 'latch_panel', view_session_date, first_viewed_ts,
           last_viewed_ts, view_count, latch_state_at_first_view, latch_state_at_last_view,
           0, 0            -- see "the legacy backfill is 0, not 1" below
    FROM latch_view_events;
DROP TABLE latch_view_events;
ALTER TABLE latch_view_events_new RENAME TO latch_view_events;
-- the three 0032 indexes + BOTH 0032 identity-coherence triggers recreated VERBATIM
```

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
  On INSERT both actionability columns take the passed value; on UPDATE `actionable_at_last_view` becomes
  `MAX(existing, new)` (monotonic `0 -> 1`, never back) and `actionable_at_first_view` is **NEVER rewritten**,
  alongside the existing monotonic `view_count` / `last_viewed_ts` advance.
- `list_views_for_latch(conn, *, candidate_id, surfaces=None)` /
  `list_views_for_session(conn, *, view_session_date, surfaces=None)` — `None` means ALL
  surfaces (a raw read); every CLASSIFICATION caller passes `surfaces=ACTIONABLE_VIEW_SURFACES` explicitly
  (§E.3), so no reader silently inherits a set it did not choose.
- `_row_to_model`, `_COLS` and **`swing/data/models.py:LatchViewEvent`** carry `surface`,
  `actionable_at_first_view` AND `actionable_at_last_view` — the model was a plain omission in the first draft
  (Codex R15 MAJOR 1), which would have left `never_actionable`, `covered_sessions` and the beacon split with
  no hydrated fields to read. `__post_init__` validates both against `{0, 1}` (the `Literal` hint is not
  runtime-enforced) and rejects `actionable_at_last_view < actionable_at_first_view` (the monotonic contract,
  mirrored from the SQL side under the #11 discipline).

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
triggers and all seven CHECKs from `0032` MUST be reproduced byte-for-byte**; a test asserts the post-`0033`
table still rejects each of the shapes `tests/data/test_migration_0032.py` proves it rejects (this is the
single largest regression risk in the arc and it gets its own task step).

**The cheaper alternative CHARC may prefer, named for a veto:** `ALTER TABLE ... ADD COLUMN
first_view_surface / last_view_surface` (no rebuild, grain unchanged). It is smaller, and it LOSES per-surface
counts — you could not tell five panel opens from one dashboard glance. The plan recommends the rebuild
because B4's stated purpose is keeping 21-F's surface architecture unconstrained, and the cheaper option
constrains it.

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
    action_session_date  TEXT NOT NULL,          -- the session the form was RENDERED for
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
    CHECK (validity_outcome <> 'accepted_by_broker'
           OR actual_order_type <> 'STOP_LIMIT' OR actual_stop_price IS NOT NULL),
    CHECK (validity_outcome <> 'accepted_by_broker'
           OR actual_order_type <> 'LIMIT'      OR actual_stop_price IS NULL),
    CHECK (derivation_sizing_basis IS NULL
           OR derivation_sizing_basis IN ('limit_price','pivot')),
    CHECK (derivation_zone_cap_pct IS NULL OR derivation_zone_cap_pct > 0),
    CHECK (derivation_sizing_equity IS NULL OR derivation_sizing_equity > 0),
    CHECK (derivation_max_risk_pct IS NULL OR derivation_max_risk_pct > 0),
    CHECK (derivation_position_pct_cap IS NULL OR derivation_position_pct_cap > 0),
    -- PAIRED NULL. A close without the session it is DATED is exactly the
    -- provenance-free number 21-G exists to eliminate; a session without a
    -- close is a claim about a price that is not there.
    CHECK ((derivation_regime_close IS NULL) = (derivation_regime_close_session IS NULL)),
    CHECK (derivation_regime_close_session IS NULL
           OR (length(derivation_regime_close_session) = 10
               AND date(derivation_regime_close_session) IS NOT NULL
               AND date(derivation_regime_close_session)
                   = derivation_regime_close_session)),
    CHECK (actual_quantity IS NULL OR actual_quantity > 0),
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
           -- object; the required keys (broker_snapshot_ts,
           -- broker_snapshot_branch, broker_snapshot_digest,
           -- attributable_order_count, exact_framework_match_count,
           -- indeterminate) are enforced in the repo + the dataclass validator
           -- under #11 AND in SQL: for an append-only audit ledger "the repo
           -- usually writes it correctly" is not enough, because a raw insert
           -- can append a row the report cannot hydrate and whose staleness
           -- basis is unknowable forever after.
           AND validity_detail IS NOT NULL
           AND json_valid(validity_detail)
           -- VALUE SHAPES, not merely presence (R24 MAJOR). The plan claims
           -- "correct value shapes" are enforced; presence-only checks let a raw
           -- append store an invalid branch, a malformed timestamp, a non-hex
           -- digest or a non-boolean flag, and an append-only ledger keeps it
           -- forever.
           AND length(json_extract(validity_detail, '$.broker_snapshot_ts')) = 19
           AND datetime(json_extract(validity_detail, '$.broker_snapshot_ts'))
               IS NOT NULL
           AND json_extract(validity_detail, '$.broker_snapshot_branch')
               IN ('presence','absence','unavailable')
           AND length(json_extract(validity_detail, '$.broker_snapshot_digest')) = 64
           AND json_extract(validity_detail, '$.broker_snapshot_digest')
               NOT GLOB '*[^0-9a-f]*'
           AND length(json_extract(validity_detail, '$.broker_snapshot_session')) = 10
           AND date(json_extract(validity_detail, '$.broker_snapshot_session'))
               IS NOT NULL
           AND json_type(validity_detail, '$.attributable_order_count') = 'integer'
           AND json_extract(validity_detail, '$.attributable_order_count') >= 0
           AND json_type(validity_detail, '$.exact_framework_match_count') = 'integer'
           AND json_extract(validity_detail, '$.exact_framework_match_count') >= 0
           AND json_type(validity_detail, '$.indeterminate')
               IN ('true','false'))),
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
       AND derivation_regime_close_session IS NULL)),
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
       AND derivation_regime_close_session IS NOT NULL)),
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
    CHECK (length(detection_date) = 10
           AND date(detection_date) IS NOT NULL
           AND date(detection_date) = detection_date),
    CHECK (length(action_session_date) = 10
           AND date(action_session_date) IS NOT NULL
           AND date(action_session_date) = action_session_date),
    -- `recorded_ts` DRIVES THE MONTHLY REPORT'S CUTOFF AND ORDERING (section
    -- F.3), so an unconstrained TEXT column lets a raw insert or a repo bug
    -- silently misbucket a monthly parity read while looking authoritative
    -- (R19 MAJOR). Local ISO seconds, exactly: YYYY-MM-DDTHH:MM:SS.
    CHECK (length(recorded_ts) = 19
           AND datetime(recorded_ts) IS NOT NULL
           AND datetime(recorded_ts) = replace(recorded_ts, 'T', ' ')),
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
        'latch_order_intents validity parent must be a place row on the same latch')
    WHERE NOT EXISTS (
        SELECT 1 FROM latch_order_intents parent
        WHERE parent.intent_id  = NEW.validated_place_intent_id
          AND parent.intent_kind = 'place'
          AND parent.candidate_id = NEW.candidate_id);
END;
```

with the matching `BEFORE UPDATE OF validated_place_intent_id, candidate_id` twin. Keying the coherence on
`candidate_id` (the immutable latch surrogate) rather than on the session is deliberate: a `place` and its
`validity` answer legitimately land in DIFFERENT sessions — that is the whole point of the aged prompt.

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
18 columns about a different subject"; the extra 16 are the derivation-input block (8, which is B1's whole
point), the actual-params block (6, which is B3's whole point), the idempotency key, and the validity parent
link. Every one is justified above; nothing is speculative. If CHARC judges
this past "minimal", the compressible group is the derivation-input block, which could collapse into one JSON
envelope — the plan does NOT recommend that (a JSON blob defeats the CHECKs, defeats indexing, and is the
`structural_evidence_json` shape the Phase-12 gotchas already burned us on).

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
| `limit_price` | `latch.zone_cap` — already `round(pivot * 1.03, 4)` from 21-A |
| `quantity` | `compute_shares(entry=limit_price, stop=latched_initial_stop, equity=sizing_equity, max_risk_pct=..., position_pct_cap=...).shares` (A.2) |

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
  two hidden fields while `validity_detail` required SIX keys, and `POST /latches/intent` is forbidden from
  borrowing Schwab so it could not reconstruct the missing four at submit time; the audit row was therefore
  either unwritable or populated from guesses). The envelope carries EXACTLY the keys `validity_detail`
  requires and `broker_snapshot_digest` covers — `broker_snapshot_ts` (SERVER-stamped at fragment render),
  `broker_snapshot_branch` (`presence`/`absence`/`unavailable`), `broker_snapshot_digest`,
  `broker_snapshot_session` (the action session the BROKER VIEW came from - distinct from the row's
  `action_session_date`, which is the MANDATE's session, section C.2), `attributable_order_count`,
  `exact_framework_match_count`, `indeterminate`. The handler VALIDATES the
  envelope (parseable, all six keys, correct value shapes — the same 4-tier ladder) and PERSISTS IT VERBATIM
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

**Precedence on the DECISION axis (each rung gets its own discriminating test):**

1. `intents` contains a `place` -> **`accepted`** (the most recent `place` wins; an earlier `decline` is
   history, not the outcome). **This says he DECIDED to place, and nothing more** — a rejected order is still
   an accepted decision, and it is `execution_outcome` that says so. A test asserts a `place` intent with
   `validity_outcome='rejected_by_broker'` yields `accepted` + `rejected_by_broker` and is EXCLUDED from the
   agreement numerator.
2. else `intents` contains a `decline` -> **`declined`**.
3. else `intents` contains an `attest` -> **`attested_<disposition>`**. `attested_was_away` is a THIRD
   terminal category (§A.1.6 ruling 2): counted in `classifiable_fires`, EXCLUDED from the discipline signal,
   and included in the ATTESTED away rate only — never merged into the objective one, because testimony is not
   telemetry (§A.0).
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
6. else if there is at least one view row with **`actionable_at_last_view = 1`** inside the covered window:
   - latch is LIVE -> **`pending_live`** (no prompt; the mandate can still be acted on). **Reported, never
     scored** (§A.1.6 ruling 1): it enters no denominator, because a latch that has not terminated is not an
     observation yet and its verdict would move as the window runs.
   - latch is TERMINAL -> **`discipline_lapse`**, with `prompt_required=True`. There is no intermediate
     state — see E.1.
7. else (no `actionable_at_last_view = 1` view row in the covered window) — **coverage is NOT re-tested here;
   reaching this rung already means the table routed to `_CLASSIFY_NORMALLY`**:
   - `verdict.awareness_established` is True (>= 1 view row, necessarily all `actionable_at_last_view = 0`)
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
train-the-dismissal-reflex failure. A parametrised test walks all ELEVEN dispositions and asserts exactly one
True — so a future disposition added without a decision about its prompt FAILS.
Rationale, recorded because it constrains future change: a prompt on an objectively-resolved cell trains
dismissal, and dismissal is what eventually kills the honest answer on the cell that matters.

### E.3 A "view" for classification means an ACTIONABLE view, ON A COUNTED SURFACE, of THIS latch while it was LIVE

Three conjuncts, each enforced somewhere different:

1. **Actionable** — the row's own `actionable_at_last_view = 1` (§C.1). NOT a write contract: the withheld
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

    FIVE buckets PARTITION the corpus: every (disposition, is_terminal) pair
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
    # COHERENCE FIRST (R24 MAJOR). `pending_live` means "the latch is LIVE", so
    # (pending_live, is_terminal=True) is not a state the classifier can
    # legitimately produce -- and silently bucketing it as pending would hide a
    # classifier bug in the very report layer built to stop silent absorption.
    if disposition in PENDING_DISPOSITIONS and is_terminal:
        raise ValueError(
            "incoherent cell: pending_live with is_terminal=True")
    # RULING 1, ENFORCED AS A GATE: a latch that has not terminated is not an
    # observation yet, WHATEVER its current display disposition says.
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
    raise ValueError(
        f"{disposition!r} has no ruled R bucket; see plan section A.1.6")

_ALL_EXCLUDED_DISPOSITIONS = frozenset({
    "away_unseen", "pre_telemetry",
    "never_actionable", "telemetry_unhealthy",
})
PENDING_DISPOSITIONS       = frozenset({"pending_live"})
ATTESTED_AWAY_DISPOSITIONS = frozenset({"attested_was_away"})

UNATTRIBUTABLE_DISPOSITIONS = (
    _ALL_EXCLUDED_DISPOSITIONS
    - AWAY_RATE_COUNTED_DISPOSITIONS
    - ATTESTED_AWAY_DISPOSITIONS
)
```

**`_ALL_EXCLUDED_DISPOSITIONS` is defined ABOVE its use** (R23 MINOR — the draft's constant order raised
`NameError` if copied literally), and `ATTESTED_AWAY_DISPOSITIONS` is subtracted too, or `away_unseen`'s
sibling would fall into `unattributable_r` as well as its own bucket.

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

`ExecutionParityReport` carries all FIVE buckets — `decision_r`, `away_r`, `attested_away_r`,
`unattributable_r`, `pending_r` — plus each excluded disposition's own count so the REASON is never lost
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
    "v1", str(candidate_id), action_session_date, surface, intent_kind,
    anchor_digest, actual_digest)
```

`anchor_digest` and `actual_digest` are built with the SAME `_digest` helper over their own component lists,
so the property holds all the way down. A test plants a `decline_reason` containing `|`, `:` and a digit run
and asserts two distinct decisions produce distinct keys.

`anchor_digest` is the canonical (sorted-key, fixed-format) serialisation of **EVERY hidden field the form
emitted** — `view_session_date`, `candidate_id`, all five `framework_*` fields and all eight `derivation_*`
fields — **exactly as SUBMITTED**. It is NOT the session anchor alone (Codex R5 MAJOR 3): if the key covered
only the session and the operator's answer, a tampered or stale form carrying a DIFFERENT framework order but
the same session and answer would hit the replay `SELECT` at step 4 and return `200` **without ever reaching
the step-5 comparison** — a laundering path straight through the hazard-(b) defence.
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
`framework_quantity`, plus the drift-capable derivation inputs (`derivation_*`). At POST:

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
4. `recorded_ts` is SERVER-STAMPED wall clock; `action_session_date` is the VALIDATED anchor. No timestamp is
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
| `swing/data/models.py` | `LatchOrderIntent` dataclass + `__post_init__`; **`LatchViewEvent` gains `surface`, `actionable_at_first_view` and `actionable_at_last_view`** with `{0,1}` + monotonicity validation; the new enums IMPORTED from `swing/latches/constants.py`, never re-declared |
| `swing/data/repos/latch_view_events.py` | RE-KEYED on `(candidate_id, view_session_date, surface)` (§C.1) — `get_view` / `record_view` take `candidate_id` + a REQUIRED `surface`; `_COLS` and `_row_to_model` gain `surface` + both actionability columns; `record_view` gains `actionable=`; both list helpers gain an explicit `surfaces=` filter |
| `swing/latches/constants.py` | `LATCH_TELEMETRY_EPOCH_SESSION`, `LATCH_VIEW_SURFACES`, `ACTIONABLE_VIEW_SURFACES`, `LATCH_INTENT_KINDS`, `LATCH_ATTESTED_DISPOSITIONS`, `LATCH_VALIDITY_OUTCOMES`, `LATCH_DISPOSITIONS`, `AWAY_RATE_COUNTED_DISPOSITIONS` (the §A.1.5 branch seam), `LATCH_SIZING_BASES`, `LATCH_STOP_LEG_STATES`, `LATCH_ORDER_WITHHELD_REASONS`, `LATCH_TELEMETRY_DARK_SESSIONS_THRESHOLD` |
| `swing/web/routes/latches.py` | **(a)** NEW `POST /latches/intent` (the §G.1 seven-step handler). **(b) `POST /latches/view` IS REWRITTEN, not merely passed a new kwarg (Codex R13 MAJOR 3):** `_parse_beacon_anchor` gains `actionable_candidate_ids` + `withheld_candidate_ids` REPLACING the single `candidate_ids` field (same rejection ladder, same 200-id cap applied to the UNION, plus a rejection when an id appears in BOTH lists); the handler intersects EACH list with the anchor-session live set and calls `record_view(..., surface="latch_panel", actionable=<which list it came from>)`. **If this route is left on the old contract every withheld render is still ingested as a plain view and the whole R7 fix never reaches the DB.** **(c)** `POST /latches/orders` gains the validity prompt + the SINGLE `broker_snapshot_json` hidden field carrying all six envelope keys (§E) — NOT separate `broker_snapshot_ts` / `broker_snapshot_branch` inputs, which cannot satisfy the six-key contract |
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
    `framework_order_type`, a bad `validity_outcome`, a malformed date (round-trip `date(x) = x`, not the
    weaker `IS NOT NULL` — the 0032 lesson).
  - `UNIQUE(idempotency_key)` blocks a second row.
  - The IMMUTABILITY BARRIER: `UPDATE` and `DELETE` on `latch_order_intents` both ABORT, and the message names
    the append-only rule.
  - A malformed `recorded_ts` (wrong length, space instead of `T`, non-datetime) is REJECTED (R19 MAJOR — this
    column drives the monthly report's cutoff and ordering); mirrored in `LatchOrderIntent.__post_init__`.
  - `actual_broker_order_id` blank-when-present is REJECTED on every kind, and a `place` or `decline` row
    carrying one at all is REJECTED (R19 MAJOR — a decision row has observed nothing).
  - A `validity` row without a non-empty, `json_valid` `validity_detail` envelope is REJECTED (R19 MAJOR); the
    required keys are enforced in the repo + dataclass validator under #11.
  - A `validity_outcome='accepted_by_broker'` row missing ANY of `actual_order_type` / `actual_duration` /
    `actual_limit_price` / `actual_quantity` is REJECTED (R20 MAJOR).
  - Every PROVENANCE CHECK: a bad `framework_duration`, a bad `derivation_sizing_basis`, a regime close
    WITHOUT its session (and the reverse), and a non-positive equity / risk pct / quantity.
  - **The FK/immutability coherence test (the R13 CRITICAL, whose assertion the R16 CRITICAL then caught the
    DDL violating):** deleting a referenced `risk_policy` row raises `IntegrityError` (RESTRICT) rather than
    attempting a SET-NULL cascade `trg_loi_no_update` would abort with a confusing message. The test PARSES
    the migration SQL and asserts the substring `SET NULL` appears NOWHERE in the `latch_order_intents`
    statement — a prose rule survived three rounds while the DDL contradicted it, so the assertion has to read
    the DDL, not the intent. It also asserts `pipeline_run_id` carries NO `REFERENCES` clause on this table
    (§C.2: the referent is legitimately pruned and the recorded identity must outlive it).
  - The VALIDITY-PARENT TRIGGER: a `validity` row pointing at a `decline` / `cancel` / `validity` row, or at a
    `place` row on a DIFFERENT `candidate_id`, is REJECTED; a `place` parent on the SAME candidate in a
    DIFFERENT session is ACCEPTED (the aged prompt is the normal case and must not be blocked).
  - **Its own red test: a `validity` row with `validated_place_intent_id = NULL` is REJECTED** (Codex R16
    MAJOR 3). The parent-link TRIGGER fires only `WHEN NEW.validated_place_intent_id IS NOT NULL`, so it is
    structurally blind to the NULL case; only the CHECK catches it, and without a test aimed at the CHECK an
    orphan validity row goes green and the parent-scoped execution-outcome model silently loses its anchor.
  - A `validity` row requires BOTH `validity_outcome` and `validated_place_intent_id`; a
    `place`/`decline`/`cancel`/`attest` row carrying any of the three validity columns is REJECTED.
  - A `validity` row MAY carry the observed `actual_*` order params (R17 CRITICAL) and MAY NOT carry any
    `framework_*` / `derivation_*` value; a `place` row MUST carry the whole drift-capable derivation block
    (a `place` with NULL `derivation_sizing_equity` is REJECTED — R17 MAJOR).
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
    detection date, pipeline twin), every CHECK, the RESTRICT, and the state enum.
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
  - A pre-`0033` row survives the rebuild carrying `surface='latch_panel'` and both actionability columns
    `= 0` (a backfill of `1` FAILS — R16 MAJOR 2); a raw INSERT of `first=1, last=0` is REJECTED by the SQL
    monotonicity CHECK (R17 MAJOR).
  - The three-mirror agreement test, parsed from the migration SQL, for **EVERY enum CHECK in `0033`** —
    `intent_kind`, `surface`, `attested_disposition`, `validity_outcome`, `framework_order_type`,
    `actual_order_type`, `framework_duration`, `actual_duration`, `derivation_sizing_basis`, and
    `latch_view_events.surface`. Each has a frozenset in `swing/latches/constants.py`, is validated in the
    dataclass `__post_init__`, and the test parses the migration SQL and asserts EXACT set equality for all of
    them, with `models.py`'s being the SAME OBJECT (`is`), not a copy. **Naming only a subset is how the #11
    rule gets violated while its own test passes** (R23 MAJOR — the draft named four of ten).
  - The backup-gate boundary matrix, all four cells: `(32,33,True)`, `(31,33,False)`, `(32,32,False)`,
    `(33,33,False)`. **The `(32,33,True)` cell is required** — without it a gate whose body is an
    unconditional `return` passes the whole test (the 21-A Codex R4-2 lesson).
  - `PHASE21_ARC_B_PRE_MIGRATION_EXPECTED_TABLES == PHASE21_ARC_A_PRE_MIGRATION_EXPECTED_TABLES |
    {"latch_view_events"}`.
  - `record_intent` idempotency: two calls with the same key return the same `intent_id` and leave ONE row.
  - `record_view(..., surface=..., actionable=...)` and `get_view(..., surface=...)` are REQUIRED kwargs (a
    call without raises `TypeError`); a same-surface replay -> ONE row `view_count=2`;
    `actionable_at_last_view` advances 0 -> 1 on update and NEVER 1 -> 0 while `actionable_at_first_view`
    never moves. **NO two-surface INSERT test at ANY level (Codex R18 MAJOR 4)** — the `surface` CHECK makes a
    second surface unwritable, so it cannot pass; the `surface` leg of the UNIQUE is proved by DDL
    introspection and real second-surface inserts belong to the future CHECK-widening migration (21-F's call).
  - A `validity` row requires BOTH `validity_outcome` and `validated_place_intent_id`, MAY carry the observed
    `actual_*` params (R17/R18 CRITICAL), and MAY NOT carry any `framework_*` / `derivation_*` value.
  - A `place` OR `decline` row MUST carry the complete framework order AND the whole drift-capable derivation
    block, and MUST NOT carry `actual_*` params (R18 MAJOR 7 — a decline is a decision ABOUT a prepared order,
    and erasing that order leaves RD unable to audit what was declined).
  - **THE FTRE DIVERGENCE INSERT, AS RAW SQL AGAINST THE REAL MIGRATION (R18 CRITICAL):** a `place` row
    (`LIMIT` / `GOOD_TILL_CANCEL` / limit 18.8902 / qty 9 / full derivation block) plus its `validity` child
    carrying observed `actual_order_type='LIMIT'`, `actual_limit_price=18.89`, `actual_quantity=10` — both
    rows must INSERT successfully — **the validity child carries `actual_duration='GOOD_TILL_CANCEL'` too**
    (R20 MAJOR: the agreement denominator needs a COMPLETE actual side, and an omitted duration makes
    `compute_order_delta` return `any_difference is None` (UNKNOWN) rather than a clean quantity mismatch, so
    FTRE would still miss the metric). The test asserts the denominator gains 1 and the numerator does not.
    The R17 fix was described in prose while the CHECK still forbade it; a
    raw-SQL migration test (not merely a repo/model test) is what makes that impossible to repeat.
  - `ACTIONABLE_VIEW_SURFACES <= LATCH_VIEW_SURFACES`, and both equal `{"latch_panel"}` today (section E.3).
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
      carry. Then every §E precedence rung; all ELEVEN dispositions' `prompt_required` (exactly one True,
      and it is `discipline_lapse`); the unattested-terminal-viewed cell's
      `effective_disposition == "discipline_lapse"`; the coverage arithmetic at all four boundaries
      (anchor == epoch, anchor == epoch - 1 session, clear == epoch, clear == epoch + 1 session); a view row
      dated inside the window but recorded against a TERMINAL state is NOT evidence (§E.3).
- [ ] **THE COVERAGE / ACTIONABILITY MATRIX — all four cells, exactly as §E states them once.** Each cell
      discriminates a different wrong implementation:
      - FULL + no awareness -> `away_unseen`.
      - FULL + awareness + only `actionable_at_last_view = 0` rows -> `never_actionable` (an implementation
        ignoring the column returns `discipline_lapse` or `away_unseen` and FAILS, in opposite directions).
      - PARTIAL + awareness + only `actionable_at_last_view = 0` rows -> `never_actionable` (an implementation
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

- [ ] **THE BUCKET PARTITION + THE GUARD RD SINGLED OUT.** Every member of `LATCH_DISPOSITIONS` maps to
      exactly one of the FIVE buckets via `r_bucket_for`; they are pairwise disjoint; the five sums reconcile
      to the corpus total; and **`r_bucket_for` RAISES on a disposition absent from all five sets** — a test
      adds a fake disposition to `LATCH_DISPOSITIONS` ONLY and asserts the raise, so a future unlisted
      disposition cannot be absorbed by a default. **Do not reintroduce a fallthrough to make this pass.**
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
- [ ] Also: a view row on a surface NOT in `ACTIONABLE_VIEW_SURFACES` does not appear in the panel's
      telemetry echo and does not move any disposition (section E.3 conjunct 2); the beacon payload carries
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
      `actionable_at_first_view` never changes on a second POST while `actionable_at_last_view` advances
      `0 -> 1` and never `1 -> 0`; the four-tier session-anchor ladder and the `409` stale notice still behave
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
